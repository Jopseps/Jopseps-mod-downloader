# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import re
import sys

from jmd import paths
from jmd.core import library
from jmd.handlers.base import GameHandler

APP_ID = 294100
_STEAM_IDS = re.compile(r"<modSteamIds>(.*?)</modSteamIds>", re.S)
_ACTIVE = re.compile(r"<activeMods>(.*?)</activeMods>", re.S)
_LI_NUM = re.compile(r"<li>\s*(\d+)\s*</li>")
_LI = re.compile(r"<li>\s*([^<\s]+)\s*</li>")
_PACKAGE_ID = re.compile(r"<packageId>\s*([^<\s]+)\s*</packageId>", re.I)


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
        for name in os.listdir(root):
            mod = os.path.join(root, name)
            about = _read(os.path.join(mod, "About", "About.xml"))
            m = _PACKAGE_ID.search(about)
            if not m:
                continue
            wid = _read(os.path.join(mod, "About", "PublishedFileId.txt")).strip()
            if not wid.isdigit():
                wid = name if name.isdigit() else ""
            if wid:
                out.setdefault(m.group(1).lower(), wid)
    return out


class RimWorldHandler(GameHandler):
    key = "rimworld"
    name = "RimWorld"
    summary = "imports .rml, saves, ModsConfig.xml"
    app_ids = (APP_ID,)
    import_filters = [("RimWorld mod list / save / ModsConfig", "*.rml *.rws *.xml"), ("Text list", "*.txt")]
    export_filters = [("Text list", "*.txt")]

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
            ids = [pmap.get(pid.lower()) for pid in _LI.findall(active.group(1))]
            return list(dict.fromkeys(i for i in ids if i))
        return []

    def default_mod_dir(self, game_dir=""):
        if game_dir:
            return os.path.join(game_dir, "Mods")
        if sys.platform == "win32":
            return r"C:\Program Files (x86)\Steam\steamapps\common\RimWorld\Mods"
        return os.path.expanduser("~/.local/share/Steam/steamapps/common/RimWorld/Mods")
