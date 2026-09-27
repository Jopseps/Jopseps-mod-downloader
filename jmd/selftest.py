# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Real-machine check: python -m jmd.selftest, or JModManager --selftest.

Runs the risky paths on this PC in a temp folder (never your profiles or mod folders): sync modes,
SteamCMD downloads of a legacy TTS item and a normal RimWorld item, TTS conversion, the PNG thumbnail.
Prints PASS / FAIL / SKIP per step and writes <data dir>/selftest.txt."""
import json
import os
import platform
import shutil
import sys
import tempfile
import time
import traceback

from jmd import handlers, paths
from jmd.core import library, models, steamcmd, sync, tts
from jmd.core.downloader import Downloader
from jmd.core.store import Store

TTS_ITEM = ("3791705100", 26378)      # Love Colored Magic: small legacy (single-file) item
RW_ITEM = ("3806038418", 4810338)     # Tech Robe: normal folder item, anonymous


class Report:
    def __init__(self):
        self.lines = []
        self.counts = {"PASS": 0, "FAIL": 0, "SKIP": 0}

    def out(self, text=""):
        self.lines.append(text)
        if sys.stdout:
            print(text, flush=True)

    def step(self, name, fn):
        t = time.time()
        try:
            detail = fn()
            status = "SKIP" if isinstance(detail, str) and detail.startswith("SKIP") else "PASS"
            if status == "SKIP":
                detail = detail[5:].strip()
        except Exception as e:  # noqa: BLE001 - every failure is a result
            status, detail = "FAIL", f"{type(e).__name__}: {e}\n" + traceback.format_exc(limit=4)
        self.counts[status] += 1
        self.out(f"[{status}] {name} ({time.time() - t:.1f}s)")
        for line in str(detail or "").rstrip().splitlines():
            self.out(f"       {line}")


def _dummy(root):
    src = os.path.join(root, "src", "42")
    os.makedirs(os.path.join(src, "About"))
    for rel in ("About/About.xml", "big.bin"):
        with open(os.path.join(src, rel), "w", encoding="utf-8") as f:
            f.write(rel)
    return src


def run():
    r = Report()
    home = os.path.expanduser("~")
    r.out(f"J Mod Manager self-test  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    r.out(f"OS {platform.platform()}  Python {sys.version.split()[0]}  frozen={getattr(sys, 'frozen', False)}")
    r.out(f"Data dir: {paths.data_dir()}")
    r.out("Runs in a temp folder. Your profiles, mod folders and SteamCMD cache are not touched.")
    r.out("")
    store = Store()
    settings = store.load_settings()
    work = tempfile.mkdtemp(prefix="jmd_selftest_")
    state = {}

    def env():
        docs = tts.documents_dir()
        ws = tts.default_workshop_dir()
        return (f"Documents: {docs} (exists={os.path.isdir(docs)})\n"
                f"TTS Workshop default: {ws} (exists={os.path.isdir(ws)})\n"
                f"Steam libraries: {library.library_folders() or 'none found'}")
    r.step("Folders (Documents / OneDrive redirect, Steam libraries)", env)

    def reg():
        keys = sorted(handlers._load())
        assert "tts" in keys, keys
        assert handlers.for_app(tts.APP_ID).key == "tts"
        return f"handlers={keys}"
    r.step("Handlers bundled", reg)

    def profiles():
        lines = []
        for p in store.load_profiles():
            h = handlers.for_app(p.app_id)
            note = f" -> will switch to '{h.key}' on next start" if p.handler == "generic" and h.key != "generic" else ""
            exists = os.path.isdir(p.mod_dir) if p.mod_dir else "n/a"
            lines.append(f"{p.name}: handler={p.handler}{note}, sync={p.sync_mode}, mod_dir exists={exists}")
            lines.append(f"    {p.mod_dir}")
        return "\n".join(lines) or "SKIP no profiles yet"
    r.step("Profiles (read only)", profiles)

    for mode in ("copy", "hardlink", "link"):
        def sync_mode(mode=mode):
            root = os.path.join(work, "sync_" + mode)
            src = _dummy(root)
            told = []
            dst = sync.sync_item(src, os.path.join(root, "Mods"), "42", mode, on_fallback=told.append)
            assert os.path.isfile(os.path.join(dst, "About", "About.xml")), "file missing after sync"
            linked = sync.is_link(dst)
            # SteamCMD prints lowercased paths on Windows: they must still resolve
            assert os.path.isdir(src.lower()) or sys.platform != "win32", "lowercased path not found"
            sync.remove(dst)
            assert os.path.isfile(os.path.join(src, "big.bin")), "remove touched the source"
            return f"ok, link={linked}" + (f", fell back to copy: {told[0]}" if told else "")
        r.step(f"Sync mode {mode}", sync_mode)

    def steamcmd_found():
        exe = steamcmd.locate(settings.steamcmd_path)
        if not exe:
            raise RuntimeError(f"not found. Searched: {settings.steamcmd_path or '-'}, {steamcmd.searched_places()}")
        state["exe"] = exe
        return exe
    r.step("SteamCMD located", steamcmd_found)

    def download():
        if "exe" not in state:
            return "SKIP no SteamCMD"
        cache = os.path.join(work, "cache")
        log, synced = [], {}

        def on_event(kind, *args):
            if kind == "log":
                log.append(args[0])
            elif kind == "status" and args[1] in (models.FAILED, models.LOGIN):
                synced[args[0]] = f"{args[1]}: {args[2].get('error', '')}"

        results = {}
        for app_id, (mod_id, size) in ((tts.APP_ID, TTS_ITEM), (294100, RW_ITEM)):
            def keep(i, path, app_id=app_id):
                synced[i] = path
                return path
            Downloader(state["exe"], cache, app_id, [(mod_id, size)], on_event, sync=keep, retries=2).run()
            results[mod_id] = synced.get(mod_id, "no result")
        state["cache"] = cache
        state["paths"] = results
        tail = "\n".join(line for line in log if "Success" in line or "ERROR" in line or "FAILED" in line)
        for mod_id, path in results.items():
            if not os.path.exists(str(path)):  # a folder, or a legacy item's _legacy.bin
                raise RuntimeError(f"{mod_id}: {path}\nSteamCMD said:\n{tail}")
        return tail + "\n" + "\n".join(f"{k} -> {v}" for k, v in results.items())
    r.step("SteamCMD downloads (legacy TTS item + RimWorld item, anonymous)", download)

    def tts_place():
        if TTS_ITEM[0] not in state.get("paths", {}):
            return "SKIP download step failed"
        workshop = os.path.join(work, "My Games", "Tabletop Simulator", "Mods", "Workshop")
        profile = models.Profile(id="t", name="TTS", app_id=tts.APP_ID, mod_dir=workshop, handler="tts")
        pngs = []
        meta = {"title": "Selftest", "preview_url": "https://example.invalid/p.jpg", "time_updated": 1,
                "save_png": lambda url, path: pngs.append((url, path))}
        dst = handlers.get("tts").place_download(profile, TTS_ITEM[0], state["paths"][TTS_ITEM[0]], meta=meta)
        with open(dst, encoding="utf-8") as f:
            save = json.load(f)
        infos = tts.read_infos(workshop)
        assert [tts.entry_id(e) for e in infos] == [TTS_ITEM[0]], infos
        assert pngs, "thumbnail hook not called"
        return f"{dst}\nSaveName={save.get('SaveName')!r}, {len(save)} keys, infos entry={infos[0]}"
    r.step("TTS conversion (BSON -> <id>.json + WorkshopFileInfos.json)", tts_place)

    def rw_place():
        if RW_ITEM[0] not in state.get("paths", {}):
            return "SKIP download step failed"
        profile = models.Profile(id="r", name="RW", app_id=294100, mod_dir=os.path.join(work, "RimWorld", "Mods"))
        dst = handlers.get("rimworld").place_download(profile, RW_ITEM[0], state["paths"][RW_ITEM[0]])
        assert os.path.isfile(os.path.join(dst, "About", "About.xml")), "About.xml missing"
        return dst
    r.step("RimWorld placement (copy into Mods)", rw_place)

    def png():
        from jmd.core import resolver
        from jmd.ui import thumbs
        try:
            from PySide6.QtGui import QGuiApplication
            if not QGuiApplication.instance():
                state["qapp"] = QGuiApplication(["selftest", "-platform", "offscreen"])
        except Exception:  # noqa: BLE001 - QImage often works without one
            pass
        url = (resolver.details([TTS_ITEM[0]]).get(TTS_ITEM[0]) or {}).get("preview_url")
        if not url:
            raise RuntimeError("Steam API gave no preview_url")
        out = os.path.join(work, "thumb.png")
        thumbs.save_png(url, out)
        with open(out, "rb") as f:
            assert f.read(8) == b"\x89PNG\r\n\x1a\n", "not a PNG"
        return f"{url} -> 256x256 PNG ({os.path.getsize(out)} bytes)"
    r.step("Thumbnail (Workshop preview -> PNG with Qt)", png)

    shutil.rmtree(work, ignore_errors=True)
    r.out("")
    r.out(f"Done: {r.counts['PASS']} passed, {r.counts['FAIL']} failed, {r.counts['SKIP']} skipped")
    r.out("Not covered here (see TESTING.md): real OneDrive folders, TTS actually listing the mod, Play button.")
    report = os.path.join(paths.ensure(paths.data_dir()), "selftest.txt")
    with open(report, "w", encoding="utf-8") as f:
        f.write("\n".join(r.lines).replace(home, "~") + "\n")
    r.out(f"Report: {report}")
    return report, r.counts["FAIL"]


def main():
    report, failed = run()
    if not sys.stdout and sys.platform == "win32":
        os.startfile(report)  # windowed build: no console to read
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
