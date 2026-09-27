# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import re
import sys

IS_WIN = sys.platform == "win32"

_TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])')


def parse_vdf(text):
    """Minimal Valve KeyValues parser (enough for libraryfolders.vdf / appmanifest_*.acf)."""
    stack = [{}]
    key = None
    for m in _TOKEN.finditer(text):
        quoted, brace = m.groups()
        if brace == "{":
            child = {}
            stack[-1][key] = child
            stack.append(child)
            key = None
        elif brace == "}":
            if len(stack) > 1:
                stack.pop()
            key = None
        elif key is None:
            key = quoted.replace("\\\\", "\\")
        else:
            stack[-1][key] = quoted.replace("\\\\", "\\")
            key = None
    return stack[0]


def _read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def steam_roots():
    """Steam client install folders on this machine."""
    home = os.path.expanduser("~")
    cands = []
    if IS_WIN:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
                cands.append(winreg.QueryValueEx(k, "SteamPath")[0])
        except OSError:
            pass
        cands += [r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"]
    else:
        cands += [os.path.join(home, ".local", "share", "Steam"), os.path.join(home, ".steam", "steam"),
                  os.path.join(home, ".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam"),
                  os.path.join(home, "Library", "Application Support", "Steam")]
    roots = []
    for c in cands:
        real = os.path.realpath(c)
        if os.path.isdir(os.path.join(real, "steamapps")) and real not in roots:
            roots.append(real)
    return roots


def library_folders():
    folders = []
    for root in steam_roots():
        data = parse_vdf(_read(os.path.join(root, "steamapps", "libraryfolders.vdf")))
        entries = data.get("libraryfolders", {})
        for entry in entries.values():
            path = entry.get("path") if isinstance(entry, dict) else None
            if path and os.path.isdir(path) and os.path.realpath(path) not in folders:
                folders.append(os.path.realpath(path))
        if root not in folders:
            folders.append(root)
    return folders


_SKIP_NAMES = ("Proton", "Steam Linux Runtime", "Steamworks Common", "SteamVR")


def installed_games():
    """[{app_id, name, install_dir}] from appmanifest_*.acf across every Steam library."""
    games = {}
    for lib in library_folders():
        apps = os.path.join(lib, "steamapps")
        try:
            names = os.listdir(apps)
        except OSError:
            continue
        for name in names:
            if not (name.startswith("appmanifest_") and name.endswith(".acf")):
                continue
            state = parse_vdf(_read(os.path.join(apps, name))).get("AppState", {})
            app_id = state.get("appid")
            title = state.get("name", "")
            if not app_id or not title or title.startswith(_SKIP_NAMES):
                continue
            games[int(app_id)] = {"app_id": int(app_id), "name": title,
                                  "install_dir": os.path.join(apps, "common", state.get("installdir", ""))}
    return sorted(games.values(), key=lambda g: g["name"].lower())


def install_dir(app_id):
    for game in installed_games():
        if game["app_id"] == int(app_id):
            return game["install_dir"]
    return ""


def process_running(names):
    """Is any process with one of these executable names running? (RimWorldLinux, RimWorldWin64.exe)"""
    wanted = {n.lower() for n in names}
    if IS_WIN:
        import subprocess
        try:
            out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=5,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        except (OSError, subprocess.SubprocessError):
            return False
        return any(line.split(",")[0].strip('"').lower() in wanted for line in out.splitlines())
    # /proc/<pid>/comm is cut at 15 characters
    short = {n[:15] for n in wanted}
    try:
        pids = [p for p in os.listdir("/proc") if p.isdigit()]
    except OSError:
        return False
    for pid in pids:
        comm = _read(os.path.join("/proc", pid, "comm")).strip().lower()
        if comm in short:
            return True
    return False
