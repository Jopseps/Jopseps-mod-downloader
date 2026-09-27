# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import shutil
from dataclasses import dataclass, field

from jmd.core import library, sync
from jmd.core.ids import extract_ids, workshop_url
from jmd.core.mods import JMM, LOCAL, STEAM, ModEntry, ModRef

DISABLED_SUFFIX = ".jmm-disabled"


@dataclass
class GameContext:
    """What a handler needs to see a game's mods; built by the controller, plain data for tests."""
    profile: object
    installed: dict = field(default_factory=dict)  # {wid: InstalledRecord}
    content_root: str = ""                         # SteamCMD cache: <cache>/steamapps/workshop/content/<app>
    libraries: list = field(default_factory=list)  # Steam library folders

    @property
    def mod_dir(self):
        return self.profile.mod_dir

    def cache_path(self, wid):
        path = os.path.join(self.content_root, wid) if self.content_root and wid else ""
        return path if path and os.path.isdir(path) else ""


def disabled_dir(mod_dir):
    """Sibling of the mod folder on the same drive, so disabling is a rename: Mods → Mods.jmm-disabled."""
    mod_dir = os.path.normpath(mod_dir)
    return mod_dir + DISABLED_SUFFIX


def _move(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        raise sync.SyncError(f"{dst} already exists")
    shutil.move(src, dst)


class GameHandler:
    """Per-game knowledge: native modlist formats, default mod folder, post-sync fixes, and how mods are
    turned on and off. Drop a module in jmd/handlers/ with a GameHandler subclass to support a new game.

    The base class is the generic manager: a mod is active when its folder sits in the mod folder.
    Disabling removes the link (link/hardlink, the cache keeps the files) or moves the folder next door
    (copy and hand-installed mods). Steam subscriptions are listed but the game loads them itself."""

    key = "generic"
    name = "Generic"
    summary = ".txt"
    app_ids = ()
    # Qt file-dialog filters: [("RimWorld mod list", "*.rml")]
    import_filters = [("Text list", "*.txt")]
    export_filters = [("Text list", "*.txt")]
    modset_import_filters = [("Text list", "*.txt")]
    supports_order = False       # load order exists and can be written
    supports_steam_toggle = False
    process_names = ()           # executable names, to warn before writing while the game runs

    def import_list(self, path):
        """Workshop IDs from a list file."""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = [line.split("#", 1)[0] for line in f]
        return extract_ids("\n".join(lines))

    def export_list(self, ids, path):
        with open(path, "w", encoding="utf-8") as f:
            for mod_id in ids:
                f.write(workshop_url(mod_id) + "\n")

    def import_modset(self, path):
        """[ModRef] from a list file, in order."""
        return [ModRef(wid=wid) for wid in self.import_list(path)]

    def default_mod_dir(self, game_dir=""):
        return os.path.join(game_dir, "Mods") if game_dir else ""

    def post_sync(self, mod_dir, mod_id):
        """Hook after a mod lands in mod_dir (e.g. write a descriptor). No-op by default."""

    @property
    def label(self):
        return f"{self.name} ({self.summary})"

    # === MANAGER ===
    def game_dir(self, ctx):
        return ctx.profile.game_dir or library.install_dir(ctx.profile.app_id)

    def game_version(self, ctx):
        return ""

    def tier(self, uid):
        """Pinned load-order tier, lower loads first."""
        return 0

    def config_path(self, ctx):
        """File that write_active edits, '' when the game keeps no such file."""
        return ""

    def can_apply(self, ctx):
        """'' when Apply works, otherwise why not."""
        return "" if ctx.mod_dir else "Set a mod folder for this profile first"

    def _folder_entry(self, ctx, path, source=None):
        name = os.path.basename(path)
        rec = ctx.installed.get(name)
        e = ModEntry(uid=name, name=rec.title if rec else name, path=path, wid=name if name.isdigit() else "",
                     source=source or (JMM if rec else LOCAL), size=rec.file_size if rec else 0)
        e.preview = rec.preview_url if rec else ""
        return e

    def _steam_roots(self, ctx):
        roots = []
        for lib in ctx.libraries:
            path = os.path.join(lib, "steamapps", "workshop", "content", str(ctx.profile.app_id))
            if os.path.isdir(path) and os.path.normpath(path) != os.path.normpath(ctx.content_root or "-"):
                roots.append(path)
        return roots

    def _subdirs(self, root):
        try:
            return [os.path.join(root, n) for n in sorted(os.listdir(root)) if os.path.isdir(os.path.join(root, n))]
        except OSError:
            return []

    def scan(self, ctx):
        """Every mod this game can see or JMM can switch on → [ModEntry] (uids may repeat across sources)."""
        out, seen = [], set()
        for root in (ctx.mod_dir, disabled_dir(ctx.mod_dir) if ctx.mod_dir else ""):
            for path in self._subdirs(root) if root else []:
                e = self._folder_entry(ctx, path)
                seen.add(e.uid)
                out.append(e)
        # downloaded but not in the mod folder: link/hardlink mods switched off, still in the cache
        for wid in ctx.installed:
            if wid not in seen and ctx.cache_path(wid):
                out.append(self._folder_entry(ctx, ctx.cache_path(wid), JMM))
        for root in self._steam_roots(ctx):
            for path in self._subdirs(root):
                e = self._folder_entry(ctx, path, STEAM)
                e.toggleable = self.supports_steam_toggle
                out.append(e)
        return out

    def read_active(self, ctx, entries):
        """Active uids as the game sees them now, in load order when the game has one."""
        mod_dir = os.path.normpath(ctx.mod_dir) if ctx.mod_dir else ""
        active = []
        for e in entries:
            if e.source == STEAM or (mod_dir and os.path.normpath(os.path.dirname(e.path)) == mod_dir):
                active.append(e.uid)
        return list(dict.fromkeys(active))

    def write_active(self, ctx, entries, uids):
        """Make the mod folder match uids. → [error text]"""
        want = set(uids)
        mod_dir = ctx.mod_dir
        off_dir = disabled_dir(mod_dir)
        mode = ctx.profile.sync_mode
        errors = []
        for e in entries:
            if not e.toggleable or e.source == STEAM:
                continue
            live = os.path.join(mod_dir, e.uid)
            parked = os.path.join(off_dir, e.uid)
            here = os.path.lexists(live)
            try:
                cache = ctx.cache_path(e.wid) if e.source == JMM and mode in ("link", "hardlink") else ""
                if e.uid in want and not here:
                    if cache and not os.path.exists(parked):
                        sync.sync_item(cache, mod_dir, e.uid, mode)
                    elif os.path.exists(parked):
                        _move(parked, live)
                    else:
                        errors.append(f"{e.title}: files not found")
                elif e.uid not in want and here:
                    if cache:
                        sync.remove(live)  # the cache still has it
                    else:
                        _move(live, parked)
            except (OSError, sync.SyncError) as err:
                errors.append(f"{e.title}: {err}")
        return errors

    def is_running(self, ctx):
        return bool(self.process_names) and library.process_running(self.process_names)
