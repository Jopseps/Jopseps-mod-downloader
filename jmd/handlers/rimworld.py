import os
import re
import sys

from jmd.handlers.base import GameHandler

_STEAM_IDS = re.compile(r"<modSteamIds>(.*?)</modSteamIds>", re.S)
_LI = re.compile(r"<li>\s*(\d+)\s*</li>")


class RimWorldHandler(GameHandler):
    key = "rimworld"
    name = "RimWorld"
    summary = "imports .rml, saves, ModsConfig.xml"
    app_ids = (294100,)
    import_filters = [("RimWorld mod list / save", "*.rml *.rws *.xml"), ("Text list", "*.txt")]
    export_filters = [("Text list", "*.txt")]

    def import_list(self, path):
        if path.lower().endswith((".rml", ".rws", ".xml")):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            block = _STEAM_IDS.search(text)
            if block:
                return [i for i in dict.fromkeys(_LI.findall(block.group(1))) if i != "0"]
            # ModsConfig.xml lists packageIds only; mapping to Workshop IDs lands in milestone 5
            return []
        return super().import_list(path)

    def default_mod_dir(self, game_dir=""):
        if game_dir:
            return os.path.join(game_dir, "Mods")
        if sys.platform == "win32":
            return r"C:\Program Files (x86)\Steam\steamapps\common\RimWorld\Mods"
        return os.path.expanduser("~/.local/share/Steam/steamapps/common/RimWorld/Mods")
