# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Right column of the Manage view: the selected mod's preview, facts, dependencies, issues and actions."""
import html
import os

from PySide6.QtCore import QRectF, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from jmd.core import ids, mods, validate
from jmd.ui.delegates import fmt_size, placeholder_brush
from jmd.ui.tokens import C, STATUS
from jmd.ui.widgets import button, hbox, label

SOURCE_TEXT = {mods.JMM: "Downloaded by JMM", mods.LOCAL: "Installed by hand", mods.STEAM: "Steam subscription",
               mods.BUILTIN: "Part of the game"}


class Preview(QWidget):
    """16:9 preview, cropped to fill."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pm = None
        self.key = ""
        self.setFixedHeight(150)

    def set_image(self, key, path):
        self.key = key
        self.pm = QPixmap(path) if path and os.path.isfile(path) else None
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(r, 3, 3)
        p.setClipPath(clip)
        if self.pm and not self.pm.isNull():
            scaled = self.pm.scaled(self.size() * 2, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            scaled.setDevicePixelRatio(2)
            sx = (scaled.width() / 2 - self.width()) / 2
            sy = (scaled.height() / 2 - self.height()) / 2
            p.drawPixmap(int(-sx), int(-sy), scaled)
        else:
            p.fillRect(r, placeholder_brush(self.key or "x", self.rect()))


class DetailsPanel(QFrame):
    selectRequested = Signal(str)   # a dependency was clicked
    webRequested = Signal(str)      # Workshop page, opened in the app's browser

    def __init__(self, mgr, parent=None):
        super().__init__(parent)
        self.mgr = mgr
        self.uid = ""
        self.setObjectName("Details")
        self.setMinimumWidth(260)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("DetailsBody")
        self.lay = QVBoxLayout(body)
        self.lay.setContentsMargins(14, 14, 14, 14)
        self.lay.setSpacing(10)
        scroll.setWidget(body)
        outer.addWidget(scroll)

        self.empty = label("Select a mod to see its details.", "dim", wrap=True)
        self.preview = Preview()
        self.name = label("", "display", wrap=True)
        self.name.setTextFormat(Qt.PlainText)
        self.name.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.meta = label("", "dim", wrap=True)
        self.facts = QLabel()
        self.facts.setWordWrap(True)
        self.facts.setTextFormat(Qt.RichText)
        self.facts.setStyleSheet("font-size:12px;")
        self.issues = QLabel()
        self.issues.setWordWrap(True)
        self.issues.setTextFormat(Qt.RichText)
        self.deps_title = label("Requires", "caps")
        self.deps = QLabel()
        self.deps.setWordWrap(True)
        self.deps.setTextFormat(Qt.RichText)
        self.deps.linkActivated.connect(self._dep_clicked)
        self.folder_btn = button("Open folder", size="sm", icon="folder", icon_size=13)
        self.web_btn = button("Workshop page", size="sm", icon="external", icon_size=13)
        self.folder_btn.clicked.connect(self._open_folder)
        self.web_btn.clicked.connect(self._open_web)
        self.desc_title = label("Description", "caps")
        self.desc = label("", "dim", wrap=True)
        self.desc.setTextFormat(Qt.PlainText)
        self.desc.setTextInteractionFlags(Qt.TextSelectableByMouse)
        for w in (self.empty, self.preview, self.name, self.meta, self.facts, self.issues):
            self.lay.addWidget(w)
        self.lay.addLayout(hbox(self.folder_btn, self.web_btn, None, spacing=6))
        for w in (self.deps_title, self.deps, self.desc_title, self.desc):
            self.lay.addWidget(w)
        self.lay.addStretch(1)
        mgr.changed.connect(self.refresh)
        mgr.stagedChanged.connect(self.refresh)
        self.show_uid("")

    def show_uid(self, uid):
        self.uid = uid
        self.refresh()

    def refresh(self):
        e = self.mgr.by_uid.get(self.uid)
        parts = (self.preview, self.name, self.meta, self.facts, self.issues, self.folder_btn, self.web_btn,
                 self.deps_title, self.deps, self.desc_title, self.desc)
        self.empty.setVisible(e is None)
        for w in parts:
            w.setVisible(e is not None)
        if e is None:
            if self.uid:
                self.empty.setText(f"{self.uid} is in the active list but isn't installed.")
            else:
                self.empty.setText("Select a mod to see its details.")
            return
        local = e.preview if e.preview and not e.preview.startswith("http") else ""
        self.preview.set_image(e.uid, local)
        self.preview.setVisible(bool(local))
        self.name.setText(e.title)
        by = f"by {e.author}" if e.author else ""
        self.meta.setText(" · ".join(x for x in (by, SOURCE_TEXT.get(e.source, "")) if x))

        rows = []
        state = "Active" if e.uid in self.mgr.staged else "Inactive"
        if e.uid in self.mgr.staged and self.mgr.ordered:
            state += f" · #{self.mgr.staged.index(e.uid) + 1}"
        rows.append(("State", state))
        if e.mod_version:
            rows.append(("Version", e.mod_version))
        if e.supported:
            rows.append(("Game", ", ".join(e.supported)))
        if e.size:
            rows.append(("Size", fmt_size(e.size)))
        rows.append(("ID", e.uid if not e.wid or e.uid == e.wid else f"{e.uid} · {e.wid}"))
        self.facts.setText("<table cellspacing=0 cellpadding=2>" + "".join(
            f"<tr><td style='color:{C['text-faint']};padding-right:10px'>{k}</td>"
            f"<td style='color:{C['text']}'>{html.escape(str(v))}</td></tr>" for k, v in rows) + "</table>")

        issues = self.mgr.issues_for(e.uid)
        self.issues.setVisible(bool(issues))
        self.issues.setText("<br>".join(
            f"<span style='color:{STATUS['failed'][1] if i.level == validate.ERROR else STATUS['outdated'][1]}'>"
            f"⚠ {html.escape(i.text)}</span>" for i in issues))

        self.deps_title.setVisible(bool(e.deps))
        self.deps.setVisible(bool(e.deps))
        link = f"color:{C['steam-blue']};text-decoration:none;"
        lines = []
        for d in e.deps:
            name = html.escape(d.name or self.mgr.title(d.uid))
            if d.uid in self.mgr.by_uid:
                mark = "✓" if d.uid in self.mgr.staged else "○"
                lines.append(f"{mark} <a style='{link}' href='{d.uid}'>{name}</a>")
            else:
                lines.append(f"<span style='color:{STATUS['failed'][1]}'>✗ {name} (not installed)</span>")
        self.deps.setText("<br>".join(lines))
        self.folder_btn.setEnabled(bool(e.path) and os.path.isdir(e.path))
        self.web_btn.setVisible(bool(e.wid))
        self.desc_title.setVisible(bool(e.description))
        self.desc.setVisible(bool(e.description))
        text = e.description.strip()
        self.desc.setText(text[:1500] + ("…" if len(text) > 1500 else ""))

    def _dep_clicked(self, uid):
        self.selectRequested.emit(uid)

    def _open_folder(self):
        e = self.mgr.by_uid.get(self.uid)
        if e and e.path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(e.path))

    def _open_web(self):
        e = self.mgr.by_uid.get(self.uid)
        if e and e.wid:
            self.webRequested.emit(ids.workshop_url(e.wid))
