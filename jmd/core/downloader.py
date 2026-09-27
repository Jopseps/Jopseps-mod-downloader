# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import threading

from jmd.core import models, steamcmd


def _dir_size(path):
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


class Downloader:
    """Downloads a batch of Workshop items with SteamCMD, retrying transient failures in fresh passes.

    Runs blocking in a worker thread. Never touches queue items: it reports through
    on_event(kind, *args):
      ("status", mod_id, status, info)   info: {"attempt", "error", "path", "bytes"}
      ("progress", mod_id, pct)
      ("log", line)
      ("prompt", kind)                   SteamCMD wants password / guard / twofactor / mobile
      ("login_failed", reason)
      ("finished", summary)              {"done", "failed", "login", "cancelled"}
    sync(mod_id, content_path) runs in the worker after each success; raising marks the item failed.
    content_path is what SteamCMD printed: the item folder, or for legacy (single-file) items the file itself,
    <id>/<hcontent>_legacy.bin.
    """

    def __init__(self, exe, install_dir, app_id, items, on_event, sync=None, retries=3,
                 username="", password="", guard=""):
        self.exe = exe
        self.install_dir = install_dir
        self.app_id = app_id
        self.sizes = {mod_id: size for mod_id, size in items}
        self.on_event = on_event
        self.sync = sync
        self.retries = max(1, retries)
        self.username = username
        self.password = password
        self.guard = guard
        self.cancelled = False
        self._run = None
        self._current = None
        self._stop_poll = threading.Event()

    # === PUBLIC ===
    def run(self):
        pending = list(self.sizes)
        done, failed, login = [], [], []
        for attempt in range(1, self.retries + 1):
            if not pending or self.cancelled:
                break
            if attempt > 1:
                for mod_id in pending:
                    self.on_event("status", mod_id, models.RETRYING, {"attempt": attempt})
            results = self._pass(pending, attempt)
            if results is None:  # login failed: nothing more this run can do
                for mod_id in pending:
                    self.on_event("status", mod_id, models.LOGIN, {"error": "Login failed"})
                login += pending
                pending = []
                break
            retry = []
            for mod_id in pending:
                outcome, info = results.get(mod_id, ("retry", {"error": steamcmd.REASON_TIMEOUT}))
                if outcome == "done":
                    done.append(mod_id)
                elif outcome == "login":
                    login.append(mod_id)
                    self.on_event("status", mod_id, models.LOGIN, info)
                elif outcome == "failed":
                    failed.append(mod_id)
                    self.on_event("status", mod_id, models.FAILED, info)
                else:
                    retry.append((mod_id, info))
            pending = [mod_id for mod_id, _ in retry]
            if attempt == self.retries:
                for mod_id, info in retry:
                    failed.append(mod_id)
                    self.on_event("status", mod_id, models.FAILED, info)
                pending = []
        if self.cancelled:
            for mod_id in pending:
                self.on_event("status", mod_id, models.QUEUED, {})
        self.on_event("finished", {"done": done, "failed": failed, "login": login, "cancelled": self.cancelled})

    def answer(self, text):
        if self._run:
            self._run.answer(text)

    def cancel(self):
        self.cancelled = True
        self._stop_poll.set()
        if self._run:
            self._run.cancel()

    # === ONE STEAMCMD PASS ===
    def _pass(self, ids, attempt):
        results = {}
        login_failed = []
        anonymous = not self.username

        def on_event(kind, *args):
            if kind == "log":
                self.on_event("log", args[0])
            elif kind == "item_start":
                self._current = args[0]
                self.on_event("status", args[0], models.DOWNLOADING, {"attempt": attempt})
                self.on_event("progress", args[0], 0.0)
            elif kind == "item_done":
                mod_id, path, size = args
                self._current = None
                results[mod_id] = self._finish(mod_id, path, size)
            elif kind == "item_error":
                mod_id, reason = args
                self._current = None
                results[mod_id] = self._classify(reason, anonymous, attempt)
            elif kind == "prompt":
                self.on_event("prompt", args[0])
            elif kind == "login_failed":
                login_failed.append(args[0])
                self.on_event("login_failed", args[0])
            elif kind == "libs_missing":
                self.on_event("log", f"Missing library: {args[0]}")

        script = steamcmd.build_script(self.install_dir, self.app_id, ids, self.username, self.password, self.guard)
        # credentials are single-use for this pass; SteamCMD caches the session afterwards
        self.password = ""
        self.guard = ""
        self._run = steamcmd.SteamCmdRun(self.exe, on_event)
        self._stop_poll.clear()
        poller = threading.Thread(target=self._poll_progress, daemon=True)
        poller.start()
        try:
            self._run.run(script)
        except OSError as e:
            self.on_event("log", f"Could not start SteamCMD: {e}")
        finally:
            self._stop_poll.set()
            poller.join(timeout=2)
            self._run = None
        if login_failed and not results:
            return None
        return results

    def _finish(self, mod_id, path, size):
        info = {"path": path, "bytes": size}
        if self.sync:
            try:
                info["path"] = self.sync(mod_id, path)
            except Exception as e:  # noqa: BLE001 - any sync failure is reported on the row
                info["error"] = f"Sync failed: {e}"
                return "failed", info
        self.on_event("progress", mod_id, 100.0)
        self.on_event("status", mod_id, models.DONE, info)
        return "done", info

    def _classify(self, reason, anonymous, attempt):
        info = {"error": reason, "attempt": attempt}
        if reason == steamcmd.REASON_NOT_FOUND:
            return "failed", info
        if reason == steamcmd.REASON_FAILURE and anonymous:
            # ownership-gated games answer "Failure"; retry once so a transient one doesn't ask for login
            if attempt >= 2 or self.retries == 1:
                return "login", info
            return "retry", info
        if reason in steamcmd.RETRYABLE or reason == steamcmd.REASON_FAILURE:
            return "retry", info
        return "failed", info

    def _poll_progress(self):
        """workshop_download_item prints no %, so watch the partial download folder grow."""
        base = steamcmd.downloads_dir(self.install_dir, self.app_id)
        last = {}
        while not self._stop_poll.wait(0.5):
            mod_id = self._current
            total = self.sizes.get(mod_id or "", 0)
            if not mod_id or total <= 0:
                continue
            got = _dir_size(os.path.join(base, mod_id))
            pct = min(99.0, got * 100.0 / total)
            if pct > last.get(mod_id, -1):
                last[mod_id] = pct
                self.on_event("progress", mod_id, pct)
