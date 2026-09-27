# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Manage view state: installed mods, the active list on disk, and the staged edit of it. Apply writes it."""
import os

from PySide6.QtCore import QObject, QTimer, Signal

from jmd.core import library, mods, rimworld, sorting, steamcmd, validate
from jmd.handlers.base import GameContext
from jmd.ui.async_task import run_async
from jmd.ui.controller import LOG_ERR


class ManagerController(QObject):
    """Owned by the main window next to AppController. Scans on a worker, mutates on the UI thread."""

    changed = Signal()          # entries rescanned (rows may appear / vanish)
    modsetChanged = Signal()    # current modset name or the saved list changed
    stagedChanged = Signal()    # staged order or issues changed
    scanningChanged = Signal(bool)

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.entries = []        # [ModEntry] as scanned, duplicates included
        self.by_uid = {}         # {uid: ModEntry}, one per uid
        self.dups = []
        self.saved = []          # active uids as on disk
        self.staged = []         # the user's edit
        self.issues = []
        self.cycles = []
        self.version = ""
        self.apply_block = ""    # why Apply can't run, '' when it can
        self.config_mtime = 0.0
        self.scanning = False
        self.modset = ""         # name of the last loaded / saved modset
        self._rescan = False
        self._backed_up = set()  # profile ids whose config got a backup this session
        self._libraries = None
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self.refresh)
        app.profileChanged.connect(self._profile_changed)
        app.installedChanged.connect(self._debounce.start)

    # === CONTEXT ===
    @property
    def handler(self):
        return self.app.handler

    @property
    def ordered(self):
        return self.handler.supports_order

    def context(self):
        p = self.app.profile
        install = self.app.install_dir()
        if not install:
            exe = self.app.steamcmd_exe()
            install = os.path.dirname(exe) if exe else ""
        if self._libraries is None:
            self._libraries = library.library_folders()
        content = steamcmd.content_dir(install, p.app_id) if install else ""
        return GameContext(p, dict(self.app.installed), content, list(self._libraries))

    # === SCAN ===
    def _profile_changed(self):
        self.modset = ""
        self.modsetChanged.emit()
        self.entries, self.by_uid, self.dups = [], {}, []
        self.saved, self.staged, self.issues, self.cycles = [], [], [], []
        self.changed.emit()
        self.stagedChanged.emit()
        self.refresh()

    def refresh(self):
        if not self.app.profile:
            return
        if self.scanning:
            self._rescan = True
            return
        self.scanning = True
        self.scanningChanged.emit(True)
        ctx = self.context()
        handler = self.handler
        pid = ctx.profile.id

        def work():
            entries = handler.scan(ctx)
            by_uid, dups = mods.index(entries)
            config = handler.config_path(ctx)
            return {"entries": entries, "by_uid": by_uid, "dups": dups,
                    "saved": handler.read_active(ctx, by_uid.values()),
                    "version": handler.game_version(ctx), "block": handler.can_apply(ctx),
                    "mtime": os.path.getmtime(config) if config and os.path.isfile(config) else 0.0}

        def done(r):
            self._scan_finished()
            if not self.app.profile or self.app.profile.id != pid:
                return
            dirty = self.dirty
            self.entries, self.by_uid, self.dups = r["entries"], r["by_uid"], r["dups"]
            self.version, self.apply_block, self.config_mtime = r["version"], r["block"], r["mtime"]
            self.saved = self._arrange(r["saved"])
            if not dirty:
                self.staged = list(self.saved)
            self._take_pending()
            self.changed.emit()
            self._staged_changed()

        def failed(err):
            self._scan_finished()
            self.app.toast.emit(f"Scan failed: {err}")

        run_async(work, done, failed)

    def _scan_finished(self):
        self.scanning = False
        self.scanningChanged.emit(False)
        if self._rescan:
            self._rescan = False
            QTimer.singleShot(0, self.refresh)

    def _arrange(self, uids):
        """Games without a load order show the active list by name."""
        if self.ordered:
            return list(uids)
        return sorted(uids, key=lambda u: self.title(u).lower())

    def _take_pending(self):
        """Mods a modset waited on: once downloaded, they join the staged list."""
        pid = self.app.profile.id
        pending = self.app.store.load_pending(pid)
        if not pending:
            return
        by_wid = {e.wid: e.uid for e in self.by_uid.values() if e.wid}
        landed = [w for w in pending if w in by_wid]
        if landed:
            self.activate([by_wid[w] for w in landed])
            self.app.store.save_pending(pid, [w for w in pending if w not in landed])

    # === QUERIES ===
    def title(self, uid):
        e = self.by_uid.get(uid)
        return e.title if e else uid

    def inactive(self):
        on = set(self.staged)
        rest = [e for e in self.by_uid.values() if e.uid not in on]
        return [e.uid for e in sorted(rest, key=lambda e: e.title.lower())]

    @property
    def changes(self):
        return mods.diff(self.saved, self.staged)

    @property
    def dirty(self):
        return self.changes.count > 0

    def issues_for(self, uid):
        return [i for i in self.issues if i.uid == uid]

    def pinned(self, uid):
        return self.ordered and self.handler.tier(uid) < 10

    # === EDIT ===
    def activate(self, uids, before=None):
        """Put uids into the active list in front of `before` (end when None). Also reorders."""
        uids = [u for u in dict.fromkeys(uids) if u in self.by_uid or u in self.staged]
        if not uids:
            return
        rest = [u for u in self.staged if u not in uids]
        at = rest.index(before) if before in rest else len(rest)
        self.staged = rest[:at] + uids + rest[at:]
        if not self.ordered:
            self.staged = self._arrange(self.staged)
        self._staged_changed()

    def deactivate(self, uids):
        locked = [u for u in uids if u in self.by_uid and not self.by_uid[u].toggleable]
        if locked:
            self.app.toast.emit(f"{self.title(locked[0])} can't be turned off here")
        drop = set(uids) - set(locked)
        if drop:
            self.staged = [u for u in self.staged if u not in drop]
            self._staged_changed()

    def auto_sort(self):
        order, self.cycles = sorting.topo_sort(self.staged, self.by_uid, self.handler.tier)
        moved = order != self.staged
        self.staged = order
        self._staged_changed()
        self.app.toast.emit("Sorted" if moved else "Already in order")

    def revert(self):
        self.staged = list(self.saved)
        self.cycles = []
        self._staged_changed()

    def _staged_changed(self):
        self.issues = validate.check(self.staged, self.by_uid, self.version, self.ordered, self.dups,
                                     self.cycles, self.handler.tier)
        self.stagedChanged.emit()

    # === MODSETS ===
    def modset_names(self):
        return self.app.store.modset_names(self.app.profile.id) if self.app.profile else []

    def save_modset(self, name):
        refs = [self.by_uid[u].ref() if u in self.by_uid else mods.ModRef(uid=u) for u in self.staged]
        self.app.store.save_modset(self.app.profile.id, mods.Modset(name=name, mods=refs))
        self.modset = name
        self.modsetChanged.emit()
        self.app.toast.emit(f'Saved modset "{name}"')

    def load_modset(self, name):
        """Stage the modset (Revert undoes it). → refs that aren't installed."""
        ms = self.app.store.load_modset(self.app.profile.id, name)
        if ms is None:
            self.app.toast.emit(f'Modset "{name}" not found')
            return []
        return self._stage_refs(ms.mods, name)

    def _stage_refs(self, refs, name):
        active, missing = mods.resolve(refs, list(self.by_uid.values()))
        locked = [u for u in self.staged if u in self.by_uid and not self.by_uid[u].toggleable and u not in active]
        self.staged = self._arrange(locked + active)
        self.cycles = []
        self.modset = name
        self.modsetChanged.emit()
        self._staged_changed()
        self.app.toast.emit(f'Loaded "{name}"' + (f" · {len(missing)} not installed" if missing else ""))
        return missing

    def import_modset(self, path):
        """Import a list file as a new modset and stage it. → missing refs."""
        try:
            refs = self.handler.import_modset(path)
        except OSError as e:
            self.app.toast.emit(f"Import failed: {e}")
            return []
        if not refs:
            self.app.toast.emit(f"No mods found in {os.path.basename(path)}")
            return []
        name = os.path.splitext(os.path.basename(path))[0]
        self.app.store.save_modset(self.app.profile.id, mods.Modset(name=name, mods=refs))
        return self._stage_refs(refs, name)

    def export_modset(self, path):
        wids = [self.by_uid[u].wid for u in self.staged if u in self.by_uid and self.by_uid[u].wid]
        skipped = len(self.staged) - len(wids)
        try:
            self.handler.export_list(wids, path)
        except OSError as e:
            self.app.toast.emit(f"Export failed: {e}")
            return
        self.app.toast.emit(f"Exported {len(wids)} mods" + (f" · {skipped} without a Workshop ID left out" if skipped else ""))

    def delete_modset(self, name):
        self.app.store.delete_modset(self.app.profile.id, name)
        if self.modset == name:
            self.modset = ""
        self.modsetChanged.emit()
        self.app.toast.emit(f'Deleted modset "{name}"')

    def download_missing(self, refs):
        """Queue downloads for refs with a Workshop id; they get staged Active once they land."""
        wids = [r.wid for r in refs if r.wid]
        if not wids:
            self.app.toast.emit("None of them has a Workshop ID to download")
            return 0
        pid = self.app.profile.id
        self.app.store.save_pending(pid, self.app.store.load_pending(pid) + wids)
        self.app.add_ids(wids)
        return len(wids)

    # === FIXES ===
    def fixable(self, issue):
        """Button text for an issue's fix, '' when there's nothing to do automatically."""
        return {validate.INACTIVE_DEP: "Activate", validate.MISSING_DEP: "Download" if issue.fix else "",
                validate.ORDER: "Auto-sort", validate.CYCLE: "", validate.NOT_INSTALLED: "Remove"}.get(issue.kind, "")

    def fix(self, issue, sort=True):
        if issue.kind == validate.INACTIVE_DEP:
            self.activate(issue.fix, before=issue.uid if self.ordered else None)
        elif issue.kind == validate.MISSING_DEP and issue.fix:
            self.download_missing([mods.ModRef(wid=w) for w in issue.fix])
        elif issue.kind == validate.ORDER and sort:
            self.auto_sort()
        elif issue.kind == validate.NOT_INSTALLED:
            self.deactivate([issue.uid])

    def fix_all(self):
        """Activate inactive dependencies, download missing ones, then sort."""
        before = len(self.issues)
        seen = set()
        for issue in list(self.issues):
            key = (issue.kind, tuple(issue.fix))
            if issue.kind in (validate.INACTIVE_DEP, validate.MISSING_DEP) and key not in seen:
                seen.add(key)
                self.fix(issue, sort=False)
        if self.ordered:
            self.auto_sort()
        self.app.toast.emit(f"Fixed {max(0, before - len(self.issues))} of {before} issues")

    # === APPLY ===
    def apply_checks(self):
        """Reasons to ask before writing: [('running' | 'changed', text)]."""
        ctx = self.context()
        asks = []
        if self.handler.is_running(ctx):
            asks.append(("running", f"{ctx.profile.name} is running. It may overwrite the change when it exits."))
        config = self.handler.config_path(ctx)
        if config and os.path.isfile(config) and os.path.getmtime(config) != self.config_mtime:
            asks.append(("changed", f"{os.path.basename(config)} changed on disk since it was loaded "
                                    "(the game or another tool)."))
        return asks

    def apply(self):
        if self.apply_block:
            self.app.toast.emit(self.apply_block)
            return False
        ctx = self.context()
        config = self.handler.config_path(ctx)
        pid = ctx.profile.id
        if config and pid not in self._backed_up:
            folder = os.path.join(self.app.store.root, "profiles", pid, "backups")
            if rimworld.backup(config, folder):
                self._backed_up.add(pid)
        entries = list(self.by_uid.values())
        errors = self.handler.write_active(ctx, entries, [u for u in self.staged if u in self.by_uid])
        if errors:
            self.app.toast.emit(errors[0] + (f" (+{len(errors) - 1} more)" if len(errors) > 1 else ""))
            for err in errors:
                self.app._log(err, LOG_ERR)
        else:
            n = len(self.staged)
            self.app.toast.emit(f"Applied · {n} active")
        self.saved = list(self.staged)
        self.refresh()
        return not errors

