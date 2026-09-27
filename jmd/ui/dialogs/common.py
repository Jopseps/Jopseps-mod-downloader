# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pieces shared by the profile dialog and onboarding: radio-style option cards and the game picker."""
import os

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from jmd import handlers
from jmd.core import library, steam_api
from jmd.core.ids import parse_game_ref
from jmd.ui import icons
from jmd.ui.async_task import run_async
from jmd.ui.tokens import C, STATUS
from jmd.ui.widgets import button, label


class Ring(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(14, 14)
        self.on = False

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(C["accent"] if self.on else C["border-strong"]), 1))
        p.drawEllipse(QRectF(0.5, 0.5, 13, 13))
        if self.on:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(C["accent"]))
            p.drawEllipse(QRectF(4, 4, 6, 6))


class OptionCard(QPushButton):
    """Radio card: ring + bold label + sub line (design: Sync mode / Cache folder)."""

    def __init__(self, title, sub, mono_sub=False, parent=None):
        super().__init__(parent)
        self.setProperty("kind", "option")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(10)
        self.ring = Ring()
        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet("font-weight:600;background:transparent;")
        self.sub = QLabel(sub)
        family = "font-family:'JetBrains Mono';font-size:11px;" if mono_sub else "font-size:12px;"
        self.sub.setStyleSheet(f"{family}color:{C['text-dim']};background:transparent;")
        self.sub.setWordWrap(True)
        col.addWidget(t)
        col.addWidget(self.sub)
        lay.addWidget(self.ring, 0, Qt.AlignTop)
        lay.addLayout(col, 1)
        for w in (self.ring, t, self.sub):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.toggled.connect(self._toggled)

    def _toggled(self, on):
        self.ring.on = on
        self.ring.update()

    def sizeHint(self):
        return QSize(200, self.layout().sizeHint().height())

    def minimumSizeHint(self):
        return QSize(100, self.layout().sizeHint().height())


class GameButton(QPushButton):
    def __init__(self, game, thumbs, parent=None):
        super().__init__(parent)
        self.game = game
        self.setProperty("kind", "game")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(38)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(10)
        self.cap = QLabel()
        self.cap.setFixedSize(54, 25)
        self.cap.setStyleSheet(f"background:{C['raised']};")
        self.cap.setScaledContents(True)
        name = QLabel(game["name"])
        name.setStyleSheet("background:transparent;")
        name.setMinimumWidth(10)
        appid = QLabel(str(game["app_id"]))
        appid.setStyleSheet(f"font-family:'JetBrains Mono';font-size:11px;color:{C['text-dim']};background:transparent;")
        lay.addWidget(self.cap)
        lay.addWidget(name, 1)
        lay.addWidget(appid)
        for w in (self.cap, name, appid):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.thumbs = thumbs
        self.load_cap()

    def load_cap(self):
        pm = self.thumbs.get_wide(f"cap_{self.game['app_id']}", self.game.get("image"), 54, 25)
        if pm:
            self.cap.setPixmap(pm)


def caps_label(text):
    lbl = label(text.upper(), "caps")
    return lbl


class GamePicker(QWidget):
    """Left: search / detected games / AppID. Right: selected game, mod folder, sync mode, handler."""
    changed = Signal()

    def __init__(self, thumbs, parent=None):
        super().__init__(parent)
        self.thumbs = thumbs
        self.selected = None
        self.detected = []
        self.setMinimumHeight(420)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # === LEFT ===
        left = QFrame()
        left.setObjectName("PickerLeft")
        left.setFixedWidth(320)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 16, 16, 16)
        ll.setSpacing(10)
        ll.addWidget(label("Pick a game", "section"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search games")
        self.search.addAction(icons.icon("search", C["text-dim"], 14), QLineEdit.LeadingPosition)
        self.search.textChanged.connect(lambda _: self._search_timer.start())
        ll.addWidget(self.search)
        self.list_label = caps_label("Detected on this PC")
        ll.addWidget(self.list_label)
        self.list_host = QWidget()
        self.list_lay = QVBoxLayout(self.list_host)
        self.list_lay.setContentsMargins(0, 0, 0, 0)
        self.list_lay.setSpacing(2)
        self.list_lay.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidget(self.list_host)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMinimumHeight(180)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget {background:transparent;}")
        ll.addWidget(scroll, 1)
        self.no_results = label("No games match. Try an AppID below.", "dim")
        self.no_results.hide()
        ll.addWidget(self.no_results)
        ll.addWidget(caps_label("AppID or link"))
        self.appid_in = QLineEdit()
        self.appid_in.setProperty("mono", "true")
        self.appid_in.setPlaceholderText("294100, store or Workshop link")
        self.appid_in.textChanged.connect(lambda _: self._appid_timer.start())
        self.appid_in.returnPressed.connect(self._do_appid)
        ll.addWidget(self.appid_in)
        self.appid_status = label("", "faint", wrap=True)
        self.appid_status.hide()
        ll.addWidget(self.appid_status)
        root.addWidget(left)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)

        # === RIGHT ===
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 16, 16, 16)
        rl.setSpacing(14)
        self.empty = label("Pick a game to set it up.")
        self.empty.setStyleSheet(f"color:{C['text-faint']};")
        self.empty.setAlignment(Qt.AlignCenter)
        rl.addWidget(self.empty, 1)
        self.detail = QWidget()
        dl = QVBoxLayout(self.detail)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(14)
        head = QHBoxLayout()
        head.setSpacing(12)
        self.sel_cap = QLabel()
        self.sel_cap.setFixedSize(92, 43)
        self.sel_cap.setScaledContents(True)
        self.sel_cap.setStyleSheet(f"background:{C['raised']};border:1px solid #000;")
        name_col = QVBoxLayout()
        name_col.setSpacing(0)
        self.sel_name = label("", "heading")
        self.sel_appid = label("", "monodim")
        name_col.addWidget(self.sel_name)
        name_col.addWidget(self.sel_appid)
        head.addWidget(self.sel_cap)
        head.addLayout(name_col, 1)
        dl.addLayout(head)
        folder_col = QVBoxLayout()
        folder_col.setSpacing(6)
        folder_col.addWidget(label("Mod folder", "section"))
        row = QHBoxLayout()
        row.setSpacing(6)
        self.folder = QLineEdit()
        self.folder.setProperty("mono", "true")
        self.folder.setStyleSheet("font-size:11.5px;")
        browse = button("Browse…")
        browse.clicked.connect(self._browse)
        row.addWidget(self.folder, 1)
        row.addWidget(browse)
        folder_col.addLayout(row)
        self.folder_hint = label("", "faint")
        folder_col.addWidget(self.folder_hint)
        dl.addLayout(folder_col)
        sync_col = QVBoxLayout()
        sync_col.setSpacing(6)
        sync_col.addWidget(label("Sync mode", "section"))
        self.copy_card = OptionCard("Copy (recommended)", "Copies each mod into the mod folder.")
        self.hard_card = OptionCard("Hardlink", "No extra space, real folders. Same drive as the cache.")
        self.link_card = OptionCard("Link", "Symlink / junction. Saves disk space.")
        sync_group = QButtonGroup(self)
        sync_group.addButton(self.copy_card)
        sync_group.addButton(self.hard_card)
        sync_group.addButton(self.link_card)
        self.copy_card.setChecked(True)
        self.link_warn = QLabel()
        warn_row = QHBoxLayout()
        warn_row.setSpacing(6)
        wi = QLabel()
        wi.setPixmap(icons.pixmap("warn", STATUS["outdated"][1], 14))
        wt = QLabel("Some games don't load linked mods. Switch to Copy if mods go missing.")
        wt.setWordWrap(True)
        wt.setStyleSheet(f"color:{STATUS['outdated'][1]};font-size:12px;")
        warn_row.addWidget(wi, 0, Qt.AlignTop)
        warn_row.addWidget(wt, 1)
        self.link_warn.setLayout(warn_row)
        self.link_warn.hide()
        self.link_card.toggled.connect(self.link_warn.setVisible)
        sync_col.addWidget(self.copy_card)
        sync_col.addWidget(self.hard_card)
        sync_col.addWidget(self.link_card)
        sync_col.addWidget(self.link_warn)
        dl.addLayout(sync_col)
        self.handler_lbl = QLabel()
        self.handler_lbl.setObjectName("Card")
        self.handler_lbl.setStyleSheet(f"#Card{{padding:8px 10px;font-size:12px;color:{C['text-dim']};}}")
        dl.addWidget(self.handler_lbl)
        dl.addStretch(1)
        rl.addWidget(self.detail, 1)
        self.detail.hide()
        root.addWidget(right, 1)

        self._search_timer = QTimer(self, singleShot=True, interval=350, timeout=self._do_search)
        self._appid_timer = QTimer(self, singleShot=True, interval=450, timeout=self._do_appid)
        thumbs.ready.connect(self._thumb_ready)
        run_async(library.installed_games, self._got_detected)

    # === LIST ===
    def _set_games(self, games, title):
        self.list_label.setText(title.upper())
        while self.list_lay.count() > 1:
            w = self.list_lay.takeAt(0).widget()
            if w:
                self.group.removeButton(w)
                w.deleteLater()
        for g in games:
            b = GameButton(g, self.thumbs)
            b.clicked.connect(lambda _, game=g: self._pick_listed(game))
            if self.selected and self.selected["app_id"] == g["app_id"]:
                b.setChecked(True)
            self.group.addButton(b)
            self.list_lay.insertWidget(self.list_lay.count() - 1, b)
        self.no_results.setVisible(not games and bool(self.search.text().strip()))

    def _got_detected(self, games):
        self.detected = [dict(g, image=steam_api.capsule_url(g["app_id"])) for g in games]
        if not self.search.text().strip():
            self._set_games(self.detected, "Detected on this PC")

    def _do_search(self):
        term = self.search.text().strip()
        if not term:
            self._set_games(self.detected, "Detected on this PC")
            return
        run_async(lambda: steam_api.search_games(term),
                  lambda res: self._set_games(res, "Results") if self.search.text().strip() == term else None,
                  lambda e: self._set_games([], "Results"))

    def _do_appid(self):
        self._appid_timer.stop()
        text = self.appid_in.text()
        ref = parse_game_ref(text)
        if not text.strip():
            self._appid_note("")
            return
        if not ref:
            self._appid_note("Paste an AppID, a store link or a Workshop link.", "warn")
            return
        self._appid_note("Looking up…")
        run_async(lambda: self._lookup(ref),
                  lambda res: self._appid_found(text, *res) if self.appid_in.text() == text else None,
                  lambda e: self._appid_note(f"Lookup failed: {e}", "error") if self.appid_in.text() == text else None)

    @staticmethod
    def _lookup(ref):
        """Worker: (app_id, store info or None, came from a Workshop link)."""
        kind, ref_id = ref
        if kind == "item":
            app_id = steam_api.app_of_item(ref_id)
            if not app_id:
                raise LookupError("no Workshop item with that ID")
            return app_id, steam_api.get_app(app_id), True
        app_id = int(ref_id)
        info = steam_api.get_app(app_id)
        if info is None:
            # a bare number with no store page may be a Workshop item ID instead
            owner = steam_api.app_of_item(ref_id)
            if owner:
                return owner, steam_api.get_app(owner), True
        return app_id, info, False

    def _appid_found(self, text, app_id, info, from_item):
        if info and info["name"]:
            self._appid_note(f"Game of that Workshop item: {info['name']}" if from_item else "")
            self.select(info)
        else:
            self._appid_note(f"No store page found for AppID {app_id}. Check the ID.", "warn")
            self.select({"app_id": app_id, "name": f"App {app_id}", "image": steam_api.capsule_url(app_id)})

    def _appid_note(self, text, tone=None):
        color = {"warn": STATUS["outdated"][1], "error": C["danger-text"]}.get(tone, C["text-dim"])
        self.appid_status.setStyleSheet(f"color:{color};font-size:12px;")
        self.appid_status.setText(text)
        self.appid_status.setVisible(bool(text))

    def _thumb_ready(self, key):
        for i in range(self.list_lay.count() - 1):
            w = self.list_lay.itemAt(i).widget()
            if isinstance(w, GameButton) and key == f"cap_{w.game['app_id']}_w":
                w.load_cap()
        if self.selected and key == f"cap_{self.selected['app_id']}_w":
            self._load_sel_cap()

    # === SELECTION ===
    def _pick_listed(self, game):
        self._appid_note("")
        self.select(game)

    def select(self, game):
        self.selected = game
        app_id = game["app_id"]
        # highlight follows the selection, also when it came from the AppID box
        self.group.setExclusive(False)
        for b in self.group.buttons():
            b.setChecked(b.game["app_id"] == app_id)
        self.group.setExclusive(True)
        self.handler = handlers.for_app(app_id)
        game_dir = next((g.get("install_dir", "") for g in self.detected if g["app_id"] == app_id), "")
        if not game_dir:
            game_dir = library.install_dir(app_id)
        self.folder.setText(self.handler.default_mod_dir(game_dir))
        if self.handler.key != "generic":
            self.folder_hint.setText(f"Suggested by the {self.handler.name} handler.")
        else:
            self.folder_hint.setText("Suggested default. Change it if your game reads mods elsewhere."
                                     if self.folder.text() else "Leave empty to keep mods in the SteamCMD folder.")
        self.sel_name.setText(game["name"])
        self.sel_appid.setText(f"AppID {app_id}")
        self.handler_lbl.setText(f'Handler: <span style="color:{C["text"]}">{self.handler.label}</span>')
        self._load_sel_cap()
        self.empty.hide()
        self.detail.show()
        self.changed.emit()

    def _load_sel_cap(self):
        pm = self.thumbs.get_wide(f"cap_{self.selected['app_id']}", self.selected.get("image"), 92, 43)
        if pm:
            self.sel_cap.setPixmap(pm)

    def _browse(self):
        start = self.folder.text() or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "Mod folder", start)
        if path:
            self.folder.setText(path)

    def sync_mode(self):
        if self.link_card.isChecked():
            return "link"
        return "hardlink" if self.hard_card.isChecked() else "copy"

    def result(self):
        g = self.selected
        return {"name": g["name"], "app_id": int(g["app_id"]), "mod_dir": self.folder.text().strip(),
                "sync_mode": self.sync_mode(), "capsule_url": g.get("image") or steam_api.capsule_url(g["app_id"])}
