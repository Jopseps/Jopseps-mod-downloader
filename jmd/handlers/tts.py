# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import shutil
import time

from jmd.core import sync, tts
from jmd.core.mods import JMM, LOCAL, ModEntry
from jmd.handlers.base import GameHandler, _move, disabled_dir


def _files(folder, uid):
    return os.path.join(folder, f"{uid}.json"), os.path.join(folder, f"{uid}.png")


class TtsHandler(GameHandler):
    """Tabletop Simulator: a mod is Mods/Workshop/<id>.json (+ <id>.png thumbnail), listed in
    WorkshopFileInfos.json. Off = both files and the entry move to Workshop.jmm-disabled."""

    key = "tts"
    name = "Tabletop Simulator"
    summary = "converts saves, WorkshopFileInfos.json"
    app_ids = (tts.APP_ID,)
    fixed_sync_mode = "copy"
    process_names = ("Tabletop Simulator.exe", "Tabletop Simulator")

    def default_mod_dir(self, game_dir=""):
        return tts.default_workshop_dir()

    def place_download(self, profile, mod_id, content_path, on_fallback=None, meta=None):
        """Straight into the Workshop folder, so TTS lists it at once; an update to a mod switched off stays off."""
        meta = meta or {}
        mod_dir = profile.mod_dir
        if not mod_dir:
            return content_path
        off = disabled_dir(mod_dir)
        live = os.path.isfile(_files(mod_dir, mod_id)[0])
        folder = off if not live and os.path.isfile(_files(off, mod_id)[0]) else mod_dir
        dst, png = _files(folder, mod_id)
        title = meta.get("title", "")
        save = tts.write_save(tts.legacy_file(content_path), dst, title, meta.get("time_updated", 0))
        save_png = meta.get("save_png")
        if save_png and meta.get("preview_url"):
            try:
                save_png(meta["preview_url"], png)
            except Exception:  # noqa: BLE001 - a missing thumbnail never fails the download
                pass
        tts.upsert_info(folder, mod_id, title or save.get("SaveName", ""), time.time())
        return dst

    # === MANAGER ===
    def scan(self, ctx):
        out = []
        for folder in (ctx.mod_dir, disabled_dir(ctx.mod_dir)) if ctx.mod_dir else ():
            try:
                names = sorted(os.listdir(folder))
            except OSError:
                continue
            infos = {tts.entry_id(e): e for e in tts.read_infos(folder)}
            for name in names:
                path = os.path.join(folder, name)
                if not name.lower().endswith(".json") or name == tts.INFOS or not os.path.isfile(path):
                    continue
                uid = name[:-5]
                rec = ctx.installed.get(uid)
                title = (rec.title if rec else "") or infos.get(uid, {}).get("Name") or tts.save_name(path) or uid
                e = ModEntry(uid=uid, name=title, path=path, wid=uid if uid.isdigit() else "",
                             source=JMM if rec else LOCAL, size=rec.file_size if rec else os.path.getsize(path))
                png = _files(folder, uid)[1]
                e.preview = png if os.path.isfile(png) else (rec.preview_url if rec else "")
                out.append(e)
        return out

    def read_active(self, ctx, entries):
        mod_dir = os.path.normpath(ctx.mod_dir) if ctx.mod_dir else ""
        return list(dict.fromkeys(e.uid for e in entries
                                  if mod_dir and os.path.normpath(os.path.dirname(e.path)) == mod_dir))

    def _switch(self, src_dir, dst_dir, e):
        src_json, src_png = _files(src_dir, e.uid)
        dst_json, dst_png = _files(dst_dir, e.uid)
        _move(src_json, dst_json)
        if os.path.isfile(src_png):
            if os.path.exists(dst_png):
                os.remove(dst_png)
            shutil.move(src_png, dst_png)
        kept = tts.drop_info(src_dir, e.uid)
        tts.upsert_info(dst_dir, e.uid, (kept or {}).get("Name") or e.name, keep=kept)

    def write_active(self, ctx, entries, uids):
        want = set(uids)
        mod_dir = ctx.mod_dir
        off = disabled_dir(mod_dir)
        errors = []
        for e in entries:
            if not e.toggleable:
                continue
            here = os.path.isfile(_files(mod_dir, e.uid)[0])
            try:
                if e.uid in want and not here:
                    if os.path.isfile(_files(off, e.uid)[0]):
                        self._switch(off, mod_dir, e)
                    else:
                        errors.append(f"{e.title}: files not found")
                elif e.uid not in want and here:
                    self._switch(mod_dir, off, e)
            except (OSError, sync.SyncError) as err:
                errors.append(f"{e.title}: {err}")
        return errors

    def remove(self, ctx, e):
        for folder in (ctx.mod_dir, disabled_dir(ctx.mod_dir)) if ctx.mod_dir else ():
            for path in _files(folder, e.uid):
                if os.path.isfile(path):
                    os.remove(path)
            tts.drop_info(folder, e.uid)
        cache = ctx.cache_path(e.wid) if e.source == JMM else ""
        if cache:
            shutil.rmtree(cache)
