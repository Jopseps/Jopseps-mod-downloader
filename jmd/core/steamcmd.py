import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import zipfile

from jmd import paths
from jmd.core import steam_api

IS_WIN = sys.platform == "win32"

BOOTSTRAP_URLS = {
    "win32": "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip",
    "linux": "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz",
    "darwin": "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_osx.tar.gz",
}

# === OUTPUT PATTERNS (verified against SteamCMD 1788292693 unless marked) ===
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_LOGIN_ECHO = re.compile(r"^(login\s+\S+)\s+\S.*$")  # SteamCMD echoes runscript lines; hide password/code
RX_ITEM_START = re.compile(r"Downloading item (\d+) \.\.\.")
RX_ITEM_OK = re.compile(r'Success\. Downloaded item (\d+) to "([^"]+)" \((\d+) bytes\)')
RX_ITEM_ERR = re.compile(r"ERROR! Download item (\d+) failed \(([^)]+)\)")
RX_LIB_MISSING = re.compile(r"error while loading shared libraries: (\S+)")
# unverified (no test account yet): login flow strings
RX_LOGIN_FAIL = re.compile(r"(?:FAILED|ERROR) \((Invalid Password|Rate Limit Exceeded|Two-factor code mismatch|Invalid Login Auth Code|Account Logon Denied|Expired Login Auth Code|[^)]*)\)")
RX_LOGIN_OK = re.compile(r"Waiting for user info\.\.\.\s*OK")
PROMPTS = [
    ("password", re.compile(r"password:\s*$", re.I)),
    ("guard", re.compile(r"Steam Guard code:\s*$", re.I)),
    ("twofactor", re.compile(r"Two-factor code:\s*$", re.I)),
    ("mobile", re.compile(r"confirm the login in the Steam Mobile app", re.I)),
]

# === FAILURE REASONS ===
REASON_TIMEOUT = "Timeout"
REASON_NOT_FOUND = "File Not Found"
REASON_FAILURE = "Failure"  # anonymous + ownership-gated game returns this within ~1s
RETRYABLE = {REASON_TIMEOUT, "Busy", "Service Unavailable", "No Connection", "Connection Timeout"}


class SteamCmdError(Exception):
    pass


class MissingLibsError(SteamCmdError):
    def __init__(self, lib, hint):
        super().__init__(f"SteamCMD can't start: {lib} is missing.")
        self.lib = lib
        self.hint = hint


# === LOCATE ===
def _exe_in(folder):
    for name in ("steamcmd.exe",) if IS_WIN else ("steamcmd.sh", "steamcmd"):
        path = os.path.join(folder, name)
        if os.path.isfile(path):
            return path
    return None


def candidates(configured=""):
    home = os.path.expanduser("~")
    out = []
    if configured:
        out.append(configured)
    out.append(paths.steamcmd_dir())
    which = shutil.which("steamcmd")
    if which:
        out.append(which)
    if IS_WIN:
        out += ["C:\\steamcmd", os.path.join(home, "steamcmd"), os.path.join(home, "Desktop", "steamcmd")]
    else:
        out += [os.path.join(home, ".steam", "steamcmd"), os.path.join(home, "Steam"),
                os.path.join(home, "steamcmd"), "/usr/games/steamcmd"]
    return out


def resolve_exe(path):
    """A file path is taken as-is; a folder is searched for the SteamCMD launcher."""
    if not path:
        return None
    path = os.path.expanduser(path)
    if os.path.isfile(path):
        return path
    if os.path.isdir(path):
        return _exe_in(path)
    return None


def locate(configured=""):
    for cand in candidates(configured):
        exe = resolve_exe(cand)
        if exe:
            return exe
    return None


def searched_places():
    return ", ".join(c.replace(os.path.expanduser("~"), "~") for c in candidates()[1:])


# === BOOTSTRAP ===
def _lib_hint():
    distro = ""
    try:
        with open("/etc/os-release", encoding="utf-8") as f:
            for line in f:
                if line.startswith(("ID=", "ID_LIKE=")):
                    distro += " " + line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    if "arch" in distro:
        return "sudo pacman -S lib32-gcc-libs"
    if "fedora" in distro or "rhel" in distro:
        return "sudo dnf install glibc.i686 libstdc++.i686"
    if "suse" in distro:
        return "sudo zypper install libstdc++6-32bit"
    return "sudo apt install lib32gcc-s1 lib32stdc++6"


def bootstrap(dest=None, progress=None):
    """Download + extract SteamCMD into dest, then run it once so it self-updates. Returns launcher path.
    progress(pct, line) is called along the way."""
    dest = dest or paths.steamcmd_dir()
    report = progress or (lambda pct, line: None)
    url = BOOTSTRAP_URLS.get(sys.platform, BOOTSTRAP_URLS["linux"])
    os.makedirs(dest, exist_ok=True)
    archive = os.path.join(dest, url.rsplit("/", 1)[-1])

    report(2, f"Downloading {os.path.basename(archive)}")
    with open(archive, "wb") as f:
        f.write(steam_api.fetch_bytes(url))
    report(45, f"Extracting to {dest}")
    if archive.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest)
    else:
        with tarfile.open(archive) as t:
            if hasattr(tarfile, "tar_filter"):
                t.extractall(dest, filter="tar")
            else:
                t.extractall(dest)
    os.remove(archive)

    exe = _exe_in(dest)
    if not exe:
        raise SteamCmdError("SteamCMD archive did not contain a launcher")
    if not IS_WIN:
        os.chmod(exe, os.stat(exe).st_mode | stat.S_IXUSR)
    report(80, "Running first-time update…")
    first_run(exe, lambda line: report(85, line))
    report(100, "Ready")
    return exe


def first_run(exe, on_line=None):
    """Run `+quit` once: lets SteamCMD update itself and surfaces missing 32-bit libs."""
    proc = subprocess.run([exe, "+quit"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          stdin=subprocess.DEVNULL, timeout=600, **_popen_flags())
    text = _ANSI.sub("", proc.stdout.decode("utf-8", "replace"))
    for line in text.splitlines():
        if on_line and line.strip():
            on_line(line.strip())
    lib = RX_LIB_MISSING.search(text)
    if lib:
        raise MissingLibsError(lib.group(1), _lib_hint())
    if proc.returncode not in (0, 7):  # 7 = normal exit after self-update restart on some builds
        raise SteamCmdError(f"SteamCMD exited with code {proc.returncode}")


def _popen_flags():
    # own process group/session: steamcmd.sh forks the real binary, and cancel must reach both
    if IS_WIN:
        return {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _kill_tree(proc, force=False):
    if proc.poll() is not None:
        return
    if IS_WIN:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        return
    import signal
    try:
        os.killpg(proc.pid, signal.SIGKILL if force else signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass


# === SCRIPT ===
def build_script(install_dir, app_id, ids, username="", password="", guard=""):
    lines = []
    if install_dir:
        lines.append(f'force_install_dir "{install_dir}"')
    if username:
        login = f"login {username}"
        if password:
            login += f" {password}"
            if guard:
                login += f" {guard}"
        lines.append(login)
    else:
        lines.append("login anonymous")
    for mod_id in ids:
        lines.append(f"workshop_download_item {app_id} {mod_id}")
    lines.append("quit")
    return "\n".join(lines) + "\n"


def content_dir(install_dir, app_id):
    return os.path.join(install_dir, "steamapps", "workshop", "content", str(app_id))


def downloads_dir(install_dir, app_id):
    return os.path.join(install_dir, "steamapps", "workshop", "downloads", str(app_id))


# === PARSER ===
class OutputParser:
    """Feeds raw stdout chunks, emits events. SteamCMD often ends messages with an ANSI reset instead
    of a newline, so a reset counts as a line break."""

    def __init__(self, emit):
        self.emit = emit
        self._tail = ""
        self._prompted = set()

    def feed(self, chunk):
        text = chunk.decode("utf-8", "replace").replace("\x1b[0m", "\n").replace("\r", "\n")
        text = self._tail + _ANSI.sub("", text)
        parts = text.split("\n")
        self._tail = parts.pop()
        for line in parts:
            self._line(line.strip())
        self._check_prompt(self._tail)

    def close(self):
        if self._tail.strip():
            self._line(self._tail.strip())
        self._tail = ""

    def _check_prompt(self, partial):
        for kind, rx in PROMPTS:
            if rx.search(partial) and kind not in self._prompted:
                self._prompted.add(kind)
                self.emit("prompt", kind)

    def _line(self, line):
        if not line:
            return
        line = _LOGIN_ECHO.sub(r"\1 ********", line)
        self.emit("log", line)
        m = RX_ITEM_OK.search(line)
        if m:
            self.emit("item_done", m.group(1), m.group(2), int(m.group(3)))
            return
        m = RX_ITEM_ERR.search(line)
        if m:
            self.emit("item_error", m.group(1), m.group(2))
            return
        m = RX_ITEM_START.search(line)
        if m:
            self.emit("item_start", m.group(1))
            return
        if RX_LOGIN_OK.search(line):
            self.emit("login_ok")
            return
        m = RX_LIB_MISSING.search(line)
        if m:
            self.emit("libs_missing", m.group(1))
            return
        if "Logging in" in line or line.startswith(("FAILED", "ERROR (")):
            m = RX_LOGIN_FAIL.search(line)
            if m and "Download item" not in line:
                self.emit("login_failed", m.group(1))
                return
        self._check_prompt(line)


# === RUNNER ===
class SteamCmdRun:
    """One SteamCMD process running a runscript. Blocking run(); call from a worker thread.
    on_event(kind, *args) is called from the reader thread."""

    def __init__(self, exe, on_event):
        self.exe = exe
        self.on_event = on_event
        self.proc = None
        self._cancelled = False
        self._lock = threading.Lock()

    def run(self, script_text):
        fd, script_path = tempfile.mkstemp(prefix="jmd_", suffix=".txt")
        try:
            # 0600 before writing: script may carry credentials for this one run
            if not IS_WIN:
                os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(script_text)
            with self._lock:
                if self._cancelled:
                    return -1
                self.proc = subprocess.Popen([self.exe, "+runscript", script_path], stdout=subprocess.PIPE,
                                             stderr=subprocess.STDOUT, stdin=subprocess.PIPE, **_popen_flags())
            parser = OutputParser(self.on_event)
            out = self.proc.stdout
            while True:
                chunk = out.read1(4096) if hasattr(out, "read1") else os.read(out.fileno(), 4096)
                if not chunk:
                    break
                parser.feed(chunk)
            parser.close()
            code = self.proc.wait()
            self.on_event("exit", code)
            return code
        finally:
            try:
                os.remove(script_path)
            except OSError:
                pass

    def answer(self, text):
        """Write a line to SteamCMD's stdin (password / Steam Guard prompt)."""
        if self.proc and self.proc.stdin and self.proc.poll() is None:
            try:
                self.proc.stdin.write((text + "\n").encode())
                self.proc.stdin.flush()
            except OSError:
                pass

    def cancel(self):
        with self._lock:
            self._cancelled = True
            proc = self.proc
        if proc and proc.poll() is None:
            _kill_tree(proc)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _kill_tree(proc, force=True)
