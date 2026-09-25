import os

from jmd.core.ids import extract_ids, workshop_url


class GameHandler:
    """Per-game knowledge: native modlist formats, default mod folder, post-sync fixes.
    Drop a module in jmd/handlers/ with a GameHandler subclass to support a new game."""

    key = "generic"
    name = "Generic"
    summary = ".txt"
    app_ids = ()
    # Qt file-dialog filters: [("RimWorld mod list", "*.rml")]
    import_filters = [("Text list", "*.txt")]
    export_filters = [("Text list", "*.txt")]

    def import_list(self, path):
        """Workshop IDs from a list file."""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = [line.split("#", 1)[0] for line in f]
        return extract_ids("\n".join(lines))

    def export_list(self, ids, path):
        with open(path, "w", encoding="utf-8") as f:
            for mod_id in ids:
                f.write(workshop_url(mod_id) + "\n")

    def default_mod_dir(self, game_dir=""):
        return os.path.join(game_dir, "Mods") if game_dir else ""

    def post_sync(self, mod_dir, mod_id):
        """Hook after a mod lands in mod_dir (e.g. write a descriptor). No-op by default."""

    @property
    def label(self):
        return f"{self.name} ({self.summary})"
