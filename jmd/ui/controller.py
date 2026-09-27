# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal

from jmd import handlers, paths
from jmd.core import models, resolver, steam_api, steamcmd
from jmd.core.downloader import Downloader
from jmd.core.models import Group, InstalledRecord, Profile, QueueState
from jmd.core.store import Store
from jmd.ui.async_task import EventPipe, run_async
from jmd.ui.tokens import STATUS

LOG_OK = STATUS["done"][1]
LOG_ERR = STATUS["failed"][1]
LOG_WARN = STATUS["retrying"][1]
LOG_LOGIN = STATUS["login"][1]


class AppController(QObject):
    """Owns app state (settings, profiles, queue, installed) and all background work.
    Every mutation happens on the UI thread; workers report back through signals."""

    queueChanged = Signal()           # structure changed (rows added/removed)
    itemChanged = Signal(str)         # one item's data changed
    installedChanged = Signal()
    profileChanged = Signal()
    runChanged = Signal()             # download run started/progressed/stopped
    checkingChanged = Signal(bool)
    logLine = Signal(str, str)        # text, color
    toast = Signal(str)
    loginEvent = Signal(str, str)     # kind (prompt:guard|prompt:twofactor|prompt:mobile|failed|ok|done), detail

    def __init__(self, store=None, parent=None):
        super().__init__(parent)
        self.store = store or Store()
        self.settings = self.store.load_settings()
        self.profiles = self.store.load_profiles()
        self.profile = None
        self.queue = QueueState()
        self.installed = {}
        self.log = []
        self.checking = False
        self.updating = {}            # id -> pct, for Installed-tab update runs
        self.fresh = set()            # ids updated this session ("✓ Updated")
        self.run = None               # {"downloader", "ids", "done", "kind"}
        self._pending_login = None
        self._visited_deps = set()
        self._hardlink_warned = False
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._save_queue)
        self._pipe = EventPipe(self._on_download_event, self)
        pid = self.settings.current_profile
        start = next((p for p in self.profiles if p.id == pid), self.profiles[0] if self.profiles else None)
        if start:
            self.switch_profile(start.id, quiet=True)

    # === PROFILES ===
    @property
    def handler(self):
        if not self.profile:
            return handlers.get("generic")
        return handlers.get(self.profile.handler)

    def create_profile(self, name, app_id, mod_dir, sync_mode, capsule_url=""):
        pid = Profile.slug_for(name, app_id)
        existing = next((p for p in self.profiles if p.id == pid), None)
        handler = handlers.for_app(app_id)
        if existing:
            existing.mod_dir, existing.sync_mode = mod_dir, sync_mode
            profile = existing
        else:
            profile = Profile(id=pid, name=name, app_id=int(app_id), mod_dir=mod_dir, sync_mode=sync_mode,
                              handler=handler.key, capsule_url=capsule_url or steam_api.capsule_url(app_id))
            self.profiles.append(profile)
        self.store.save_profiles(self.profiles)
        self.switch_profile(profile.id, quiet=True)
        return profile

    def save_profile(self, profile):
        """After editing a profile's fields in place."""
        self.store.save_profiles(self.profiles)
        self.toast.emit(f"Saved {profile.name} settings")

    def switch_profile(self, pid, quiet=False):
        if self.run:
            self.toast.emit("Finish or cancel the download first")
            return
        if self.profile:
            self._save_queue()
        self.profile = next(p for p in self.profiles if p.id == pid)
        self.settings.current_profile = pid
        self.store.save_settings(self.settings)
        self.queue = self.store.load_queue(pid)
        self.installed = self.store.load_installed(pid)
        migrated = self.store.migrate_lists(pid)
        self.updating.clear()
        self.fresh.clear()
        self._visited_deps = {i.id for i in self.queue.items()}
        # anything still resolving from a previous session gets resolved again
        stale = [i.id for i in self.queue.items() if i.status == models.RESOLVING]
        if stale:
            self._fetch_details(stale)
        self.profileChanged.emit()
        self.queueChanged.emit()
        self.installedChanged.emit()
        if migrated:
            self.toast.emit(f"Saved lists moved to modsets: {', '.join(migrated)}")
        elif not quiet:
            self.toast.emit(f"Switched to {self.profile.name}")

    def save_settings(self):
        self.store.save_settings(self.settings)

    # === QUEUE: ADD ===
    def add_ids(self, ids, with_deps=True):
        if not self.profile:
            self.toast.emit("Create a profile first")
            return 0
        fresh = [i for i in ids if not self.queue.has(i)]
        if not fresh:
            self.toast.emit("Already in list")
            return 0
        for mod_id in fresh:
            self.queue.add_item(mod_id)
        self._changed()

        def done(result):
            collections, plain = result
            item_ids = list(plain)
            for cid, title, children in collections:
                self.queue.remove_id(cid)
                group = self.queue.add_group(cid, title, children)
                if group:
                    item_ids += [i.id for i in group.items]
            self._changed()
            self._fetch_details(item_ids, deps_for=plain if with_deps else [])
            if collections and not plain:
                n = sum(len(self.queue.group(c).items) for c, _, _ in collections if self.queue.group(c))
                self.toast.emit(f"Added collection ({n})")
            elif len(fresh) > 1:
                self.toast.emit(f"Added {len(fresh)} mods")

        def failed(err):
            self._log(f"Could not reach Steam: {err}", LOG_ERR)
            self._fetch_details(fresh, deps_for=fresh if with_deps else [])

        run_async(lambda: resolver.classify(fresh), done, failed)
        return len(fresh)

    def add_collection(self, cid, title, child_ids):
        """Browser path: page already knows the children."""
        if self.queue.group(cid):
            self.toast.emit("Collection already in list")
            return
        group = self.queue.add_group(cid, title, child_ids)
        self._changed()
        self._fetch_details([i.id for i in group.items])
        self.toast.emit(f"Added collection ({len(group.items)})")

    def _fetch_details(self, ids, deps_for=()):
        if not ids:
            return

        def done(info):
            app_id = self.profile.app_id if self.profile else 0
            added = []
            for mod_id in ids:
                item = self.queue.find(mod_id)
                if not item:
                    continue
                d = info.get(mod_id)
                if not d or not d["ok"]:
                    item.status, item.error, item.blocked = models.FAILED, "Not found", True
                    item.title = item.title or mod_id
                else:
                    item.title = d["title"] or item.title
                    item.preview_url = d["preview_url"]
                    item.file_size = d["file_size"]
                    item.time_updated = d["time_updated"]
                    item.app_id = d["app_id"]
                    if d["app_id"] and app_id and d["app_id"] != app_id:
                        item.status, item.error = models.FAILED, f"Other game (AppID {d['app_id']})"
                        item.blocked = True
                    else:
                        item.status = models.QUEUED
                        added.append(item)
                for dep in item.deps:
                    dep.required_by = item.title
                self.itemChanged.emit(mod_id)
            self._schedule_save()
            for item in added:
                if item.id in deps_for:
                    self._fetch_deps(item)

        def failed(err):
            self._log(f"Details lookup failed: {err}", LOG_ERR)
            for mod_id in ids:
                item = self.queue.find(mod_id)
                if item and item.status == models.RESOLVING:
                    item.status, item.error = models.FAILED, "Steam unreachable"
                    item.title = item.title or mod_id
                    self.itemChanged.emit(mod_id)

        run_async(lambda: resolver.details(ids), done, failed)

    def _fetch_deps(self, item):
        if item.id in self._visited_deps:
            return
        self._visited_deps.add(item.id)

        def done(deps):
            parent = self.queue.find(item.id)
            if not parent:
                return
            new = []
            for dep_id, dep_title in deps:
                dep = self.queue.add_dep(parent, dep_id, dep_title)
                if dep:
                    new.append(dep_id)
            if new:
                self._changed()
                self.toast.emit(f"Added {parent.title} + {len(new)} required")
                self._fetch_details(new, deps_for=new)

        run_async(lambda: resolver.required(item.id), done)

    # === QUEUE: EDIT ===
    def toggle_checked(self, node):
        if isinstance(node, Group):
            on = not all(i.checked for i in node.items)
            for i in node.items:
                i.checked = on
            self.queueChanged.emit()
        else:
            node.checked = not node.checked
            self.itemChanged.emit(node.id)
        self._schedule_save()

    def toggle_open(self, group):
        group.open = not group.open
        self._changed()

    def remove(self, node):
        if self.run and not isinstance(node, Group) and node.id in self.run["ids"]:
            self.toast.emit("Can't remove while downloading")
            return
        self.queue.remove(node)
        self._changed()

    def remove_id(self, mod_id):
        if self.queue.remove_id(mod_id):
            self._changed()

    def _changed(self):
        self.queueChanged.emit()
        self._schedule_save()

    def _schedule_save(self):
        self._save_timer.start()

    def _save_queue(self):
        if self.profile:
            self.store.save_queue(self.profile.id, self.queue)

    # === LIST FILES ===
    def clear_queue(self):
        if self.run:
            self.toast.emit("Finish or cancel the download first")
            return
        self.queue = QueueState()
        self._changed()
        self.toast.emit("Cleared queue")

    def import_file(self, path):
        try:
            ids = self.handler.import_list(path)
        except OSError as e:
            self.toast.emit(f"Import failed: {e}")
            return
        fresh = [i for i in ids if not self.queue.has(i)]
        if not fresh:
            self.toast.emit(f"Nothing new in {os.path.basename(path)}")
            return
        self.add_ids(fresh)
        self.toast.emit(f"Imported {len(fresh)} mods from {os.path.basename(path)}")

    def export_file(self, path):
        ids = [i.id for i in self.queue.items() if i.checked]
        try:
            self.handler.export_list(ids, path)
        except OSError as e:
            self.toast.emit(f"Export failed: {e}")
            return
        self.toast.emit(f"Exported {len(ids)} mods to {os.path.basename(path)}")

    # === DOWNLOAD ===
    def steamcmd_exe(self):
        return steamcmd.locate(self.settings.steamcmd_path)

    def install_dir(self):
        if self.settings.cache_mode == "existing":
            return ""
        return paths.ensure(paths.cache_dir())

    def _sync_fn(self):
        profile = self.profile
        handler = self.handler

        def do_sync(mod_id, content_path):
            return handler.place_download(profile, mod_id, content_path, self._hardlink_fallback)
        return do_sync

    def _hardlink_fallback(self, reason):
        """Runs on the download thread; signals queue over to the UI thread."""
        if not self._hardlink_warned:
            self._hardlink_warned = True
            self.toast.emit("Hardlink needs the cache on the same drive. Copying instead.")
        self.logLine.emit(f"Hardlink unavailable ({reason}), copied instead", LOG_WARN)

    def download(self, items=None, username="", password="", guard="", kind="queue"):
        if self.run:
            return
        exe = self.steamcmd_exe()
        if not exe:
            self.toast.emit("SteamCMD not found. Set it in Settings.")
            return
        if items is None:
            items = [i for i in self.queue.pending() if i.status != models.LOGIN]
        if not items:
            return
        for item in items:
            item.status, item.error, item.progress, item.attempt = models.QUEUED, "", 0.0, 0
        ids = [i.id for i in items]
        dl = Downloader(exe, self.install_dir(), self.profile.app_id, [(i.id, i.file_size) for i in items],
                        self._pipe, sync=self._sync_fn(), retries=self.settings.retries,
                        username=username, password=password, guard=guard)
        self.run = {"downloader": dl, "ids": ids, "done": 0, "kind": kind, "profile": self.profile.id}
        who = f"user '{username}'" if username else "anonymous"
        self._log(f"Downloading {len(ids)} items for AppID {self.profile.app_id} ({who})")
        self.queueChanged.emit()
        self.runChanged.emit()
        threading.Thread(target=dl.run, daemon=True, name="steamcmd").start()

    def retry_failed(self):
        items = [i for i in self.queue.items() if i.status == models.FAILED and i.checked and not i.blocked]
        self.download(items)

    def retry_item(self, item):
        self.download([item])

    def cancel(self):
        if self.run:
            self.run["downloader"].cancel()
            self._log("Cancelled by user.", LOG_WARN)

    def login_items(self):
        return [i for i in self.queue.items() if i.status == models.LOGIN]

    def login(self, username, password):
        if self.run and self.run["kind"] == "login":
            # a previous attempt is stuck on a prompt: stop it, retry once it has exited
            self._pending_login = (username, password)
            self.run["downloader"].cancel()
            return
        if self.run:
            self.loginEvent.emit("failed", "Wait for the current download to finish")
            return
        items = self.login_items()
        if not items:
            self.loginEvent.emit("done", "0")
            return
        self.settings.username = username
        self.save_settings()
        self._log(f"Logging in user '{username}' to Steam Public...")
        self.download(items, username=username, password=password, kind="login")

    def answer_prompt(self, text):
        if self.run:
            self.run["downloader"].answer(text)

    def run_progress(self):
        if not self.run:
            return 0, 0, 0.0
        ids = self.run["ids"]
        total = len(ids)
        done = self.run["done"]
        partial = 0.0
        for mod_id in ids:
            item = self.queue.find(mod_id)
            if item and item.status == models.DOWNLOADING:
                partial += item.progress / 100.0
        return done, total, (done + partial) * 100.0 / max(1, total)

    def _item_for_event(self, mod_id):
        if self.run and self.run["kind"] == "update":
            return None
        return self.queue.find(mod_id)

    def _on_download_event(self, kind, *args):
        run = self.run
        if run is None:
            return
        if kind == "log":
            line = args[0]
            color = LOG_OK if line.startswith("Success") else LOG_ERR if line.startswith(("ERROR", "FAILED")) else ""
            self._log(line, color)
        elif kind == "status":
            mod_id, status, info = args
            if run["kind"] == "update":
                self._update_status(mod_id, status, info)
                return
            item = self.queue.find(mod_id)
            if not item:
                return
            item.status = status
            item.attempt = info.get("attempt", item.attempt)
            item.error = info.get("error", "") if status in (models.FAILED, models.LOGIN) else ""
            if status == models.RETRYING:
                self._log(f"Retrying item {mod_id} (attempt {item.attempt}/{self.settings.retries})", LOG_WARN)
            elif status == models.LOGIN:
                self._log("Item needs an account that owns the app. Waiting for login.", LOG_LOGIN)
            elif status == models.DONE:
                run["done"] += 1
                item.progress = 100.0
                self.installed[mod_id] = InstalledRecord.from_item(item)
                self.fresh.add(mod_id)
                if run["kind"] == "login":
                    self.loginEvent.emit("ok", "")
            self.itemChanged.emit(mod_id)
            self.runChanged.emit()
        elif kind == "progress":
            mod_id, pct = args
            if run["kind"] == "update":
                if mod_id in self.updating:
                    self.updating[mod_id] = pct
                    self.installedChanged.emit()
                return
            item = self.queue.find(mod_id)
            if item:
                item.progress = pct
                self.itemChanged.emit(mod_id)
                self.runChanged.emit()
        elif kind == "prompt":
            if args[0] == "password":
                # no password to give (cached session missing): SteamCMD would wait on stdin forever
                run["downloader"].cancel()
            self.loginEvent.emit("prompt:" + args[0], "")
        elif kind == "login_failed":
            self._log(f"FAILED ({args[0]})", LOG_ERR)
            run["downloader"].cancel()
            self.loginEvent.emit("failed", args[0])
        elif kind == "finished":
            self._finish_run(args[0])

    def _finish_run(self, summary):
        run = self.run
        self.run = None
        if run["kind"] == "login":
            # cancelled login attempts put items back to queued; they still need a login
            for mod_id in run["ids"]:
                item = self.queue.find(mod_id)
                if item and item.status == models.QUEUED:
                    item.status = models.LOGIN
        self.store.save_installed(self.profile.id, self.installed)
        self._schedule_save()
        done, failed, login = len(summary["done"]), len(summary["failed"]), len(summary["login"])
        if run["kind"] == "update":
            self.updating.clear()
            self.installedChanged.emit()
            self.toast.emit(f"Updated {done} mods" + (f" · {failed} failed" if failed else ""))
        elif summary["cancelled"]:
            if run["kind"] != "login":
                self.toast.emit(f"Cancelled · {done} done")
        else:
            msg = f"Downloaded {done}"
            if failed:
                msg += f" · {failed} failed"
            if login:
                msg += f" · {login} need login"
            self.toast.emit(msg)
        self.installedChanged.emit()
        self.queueChanged.emit()
        self.runChanged.emit()
        if run["kind"] == "login":
            pending, self._pending_login = self._pending_login, None
            if pending:
                self.login(*pending)
            else:
                self.loginEvent.emit("done", str(done))

    # === INSTALLED / UPDATES ===
    def check_updates(self):
        if self.checking or not self.installed:
            return
        self.checking = True
        self.checkingChanged.emit(True)
        ids = list(self.installed)

        def done(info):
            self.checking = False
            n = 0
            for mod_id, d in info.items():
                rec = self.installed.get(mod_id)
                if rec and d["ok"]:
                    rec.remote_updated = d["time_updated"]
                    if rec.outdated:
                        n += 1
            self.store.save_installed(self.profile.id, self.installed)
            self.checkingChanged.emit(False)
            self.installedChanged.emit()
            self.toast.emit(f"{n} updates available" if n else "All mods up to date")

        def failed(err):
            self.checking = False
            self.checkingChanged.emit(False)
            self.toast.emit(f"Update check failed: {err}")

        run_async(lambda: resolver.details(ids), done, failed)

    def outdated(self):
        return [r for r in self.installed.values() if r.outdated]

    def update_all(self):
        self.update_ids([r.id for r in self.outdated()])

    def update_ids(self, ids):
        """Re-download these installed mods (Update all, or one from the details panel)."""
        recs = [self.installed[i] for i in ids if i in self.installed]
        if not recs or self.run:
            return
        exe = self.steamcmd_exe()
        if not exe:
            self.toast.emit("SteamCMD not found. Set it in Settings.")
            return
        self.updating = {r.id: 0.0 for r in recs}
        dl = Downloader(exe, self.install_dir(), self.profile.app_id, [(r.id, r.file_size) for r in recs],
                        self._pipe, sync=self._sync_fn(), retries=self.settings.retries)
        self.run = {"downloader": dl, "ids": [r.id for r in recs], "done": 0, "kind": "update",
                    "profile": self.profile.id}
        self._log(f"Updating {len(recs)} items for AppID {self.profile.app_id}")
        self.installedChanged.emit()
        self.runChanged.emit()
        threading.Thread(target=dl.run, daemon=True, name="steamcmd-update").start()

    def _update_status(self, mod_id, status, info):
        rec = self.installed.get(mod_id)
        if not rec:
            return
        if status == models.DONE:
            rec.time_updated = rec.remote_updated
            rec.synced_at = int(time.time())
            self.updating.pop(mod_id, None)
            self.fresh.add(mod_id)
            self.run["done"] += 1
            self._log(f"Success. Downloaded item {mod_id} (update)", LOG_OK)
        elif status in (models.FAILED, models.LOGIN):
            self.updating.pop(mod_id, None)
        self.installedChanged.emit()
        self.runChanged.emit()

    # === LOG ===
    def _log(self, text, color=""):
        self.log.append((text, color))
        if len(self.log) > 2000:
            del self.log[:500]
        self.logLine.emit(text, color)

    def clear_log(self):
        self.log.clear()
