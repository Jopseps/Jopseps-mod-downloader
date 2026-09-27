# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import re
import sys

from jmd import paths
from jmd.core import library, sync, validate
from jmd.core import rimworld as rw
from jmd.core.mods import JMM, LOCAL, STEAM, ModRef, norm_uid
from jmd.handlers.base import GameHandler

APP_ID = rw.APP_ID
_STEAM_IDS = re.compile(r"<modSteamIds>(.*?)</modSteamIds>", re.S)
_ACTIVE = re.compile(r"<activeMods>(.*?)</activeMods>", re.S)
_LI_NUM = re.compile(r"<li>\s*(\d+)\s*</li>")
_LI = re.compile(r"<li>\s*([^<\s]+)\s*</li>")


def _read(path):
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def mod_roots():
    """Folders that may hold RimWorld mods: the game's Mods dir, Steam's workshop content, our cache."""
    roots = []
    game = library.install_dir(APP_ID)
    if game:
        roots.append(os.path.join(game, "Mods"))
    for lib in library.library_folders():
        roots.append(os.path.join(lib, "steamapps", "workshop", "content", str(APP_ID)))
    roots.append(os.path.join(paths.cache_dir(), "steamapps", "workshop", "content", str(APP_ID)))
    return [r for r in roots if os.path.isdir(r)]


def package_map(roots=None):
    """{packageid (lowercase): workshop id} from each mod's About/About.xml + PublishedFileId.txt."""
    out = {}
    for root in roots if roots is not None else mod_roots():
        for e in rw.scan_folder(root, LOCAL):
            if e.wid:
                out.setdefault(e.uid, e.wid)
    return out


class RimWorldHandler(GameHandler):
    key = "rimworld"
    name = "RimWorld"
    summary = "imports .rml, saves, ModsConfig.xml"
    app_ids = (APP_ID,)
    import_filters = [("RimWorld mod list / save / ModsConfig", "*.rml *.rws *.xml"), ("Text list", "*.txt")]
    export_filters = [("Text list", "*.txt")]
    modset_import_filters = [("ModsConfig.xml", "*.xml"), ("Text list", "*.txt")]
    supports_order = True
    supports_steam_toggle = True
    process_names = ("RimWorldLinux", "RimWorldWin64.exe", "RimWorldWin.exe")

    def import_list(self, path):
        if not path.lower().endswith((".rml", ".rws", ".xml")):
            return super().import_list(path)
        text = _read(path)
        # .rml mod lists, .rws saves and RimSort exports carry Workshop IDs directly
        block = _STEAM_IDS.search(text)
        if block:
            return [i for i in dict.fromkeys(_LI_NUM.findall(block.group(1))) if i != "0"]
        # ModsConfig.xml only has packageIds: map them through locally installed mods
        active = _ACTIVE.search(text)
        if active:
            pmap = package_map()
            ids = [pmap.get(norm_uid(pid)) for pid in _LI.findall(active.group(1))]
            return list(dict.fromkeys(i for i in ids if i))
        return []

    def import_modset(self, path):
        if path.lower().endswith(".xml"):
            pmap = package_map()
            uids = dict.fromkeys(norm_uid(u) for u in rw.read_active(path))
            return [ModRef(uid=u, wid=pmap.get(u, "")) for u in uids if u]
        return super().import_modset(path)

    def default_mod_dir(self, game_dir=""):
        if game_dir:
            return os.path.join(game_dir, "Mods")
        if sys.platform == "win32":
            return r"C:\Program Files (x86)\Steam\steamapps\common\RimWorld\Mods"
        return os.path.expanduser("~/.local/share/Steam/steamapps/common/RimWorld/Mods")

    # === MANAGER ===
    def place_download(self, profile, mod_id, content_path, on_fallback=None, meta=None):
        """Always into the mod folder: ModsConfig.xml, not the folder, decides what's active."""
        if not profile.mod_dir:
            return content_path
        dst = sync.sync_item(content_path, profile.mod_dir, mod_id, profile.sync_mode, on_fallback)
        self.post_sync(profile.mod_dir, mod_id)
        return dst

    def game_version(self, ctx):
        return rw.game_version(self.game_dir(ctx))

    def tier(self, uid):
        return rw.tier(uid)

    def config_path(self, ctx):
        return ctx.profile.config_path or rw.find_config(ctx.libraries)

    def can_apply(self, ctx):
        if not self.config_path(ctx):
            return "ModsConfig.xml not found. Start RimWorld once, or set its path in Profile settings."
        return ""

    def scan(self, ctx):
        """Core + DLC, the mod folder (and <game>/Mods if different), Steam subscriptions.
        RimWorld reads all of them itself, so no folder moves: ModsConfig.xml decides what's on."""
        version = validate.short_version(self.game_version(ctx))
        game = self.game_dir(ctx)
        out = rw.scan_builtin(game, version)
        folders = [ctx.mod_dir] if ctx.mod_dir else []
        game_mods = os.path.join(game, "Mods") if game else ""
        if game_mods and os.path.realpath(game_mods) not in {os.path.realpath(f) for f in folders}:
            folders.append(game_mods)
        for root in folders:
            for e in rw.scan_folder(root, LOCAL, version):
                rec = ctx.installed.get(e.wid)
                if rec and os.path.basename(e.path) == e.wid:
                    e.source, e.size = JMM, rec.file_size
                out.append(e)
        for root in self._steam_roots(ctx):
            out += rw.scan_folder(root, STEAM, version)
        return out

    def read_active(self, ctx, entries):
        path = self.config_path(ctx)
        return list(dict.fromkeys(norm_uid(u) for u in rw.read_active(path))) if path else []

    def write_active(self, ctx, entries, uids):
        path = self.config_path(ctx)
        if not path:
            return [self.can_apply(ctx)]
        try:
            rw.write_active(path, uids)
        except OSError as e:
            return [f"Couldn't write {path}: {e}"]
        return []
