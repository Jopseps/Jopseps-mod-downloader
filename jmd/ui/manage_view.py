# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Manage mode: Inactive | Active | Details columns, staged edits, Apply / Revert."""
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox, QSplitter, QVBoxLayout,
                               QWidget)

from jmd.core import ids, validate
from jmd.ui import icons
from jmd.ui.details_panel import DetailsPanel
from jmd.ui.mod_list import ModDelegate, ModListModel, ModListView
from jmd.ui.tokens import C, SIZE, STATUS
from jmd.ui.widgets import Spinner, button, icon_button, label, restyle


class Column(QFrame):
    """Header (title, count, extras) + filter box + list."""

    def __init__(self, title, mgr, thumbs, side, parent=None):
        super().__init__(parent)
        self.setObjectName("ModColumn")
        self.model = ModListModel(mgr, side, self)
        self.view = ModListView(self.model, ModDelegate(mgr, thumbs, side))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        head = QFrame()
        head.setObjectName("ColHeader")
        head.setFixedHeight(SIZE["tabs"])
        self.head = QHBoxLayout(head)
        self.head.setContentsMargins(12, 0, 8, 0)
        self.head.setSpacing(8)
        self.title = label(title, "strong")
        self.count = label("0", "badge")
        self.head.addWidget(self.title)
        self.head.addWidget(self.count)
        self.head.addStretch(1)
        lay.addWidget(head)
        box = QFrame()
        box.setObjectName("ColFilter")
        bl = QHBoxLayout(box)
        bl.setContentsMargins(8, 6, 8, 6)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter")
        self.filter.setClearButtonEnabled(True)
        self.filter.addAction(icons.icon("search", C["text-faint"], 14), QLineEdit.LeadingPosition)
        self.filter.textChanged.connect(self.model.set_filter)
        bl.addWidget(self.filter)
        lay.addWidget(box)
        lay.addWidget(self.view, 1)
        self.model.modelReset.connect(self._count)
        self._count()

    def _count(self):
        total = len(self.model.all_uids())
        shown = len(self.model.rows)
        self.count.setText(f"{shown}/{total}" if shown != total else str(total))


class ManageView(QFrame):
    webRequested = Signal(str)

    def __init__(self, mgr, thumbs, parent=None):
        super().__init__(parent)
        self.mgr = mgr
        self.setObjectName("ManageView")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # === BANNER === (why Apply can't run)
        self.banner = QLabel()
        self.banner.setObjectName("InfoBanner")
        self.banner.setWordWrap(True)
        self.banner.hide()
        root.addWidget(self.banner)

        # === COLUMNS ===
        self.inactive = Column("Inactive", mgr, thumbs, "inactive")
        self.active = Column("Active", mgr, thumbs, "active")
        self.spinner = Spinner()
        self.spinner.hide()
        self.inactive.head.insertWidget(3, self.spinner)
        self.sort_btn = button("Auto-sort", "ghost", "sm", icon="sort", icon_size=13,
                               tooltip="Sort by each mod's load rules (Harmony, Core and DLC stay on top)")
        self.sort_btn.clicked.connect(mgr.auto_sort)
        self.active.head.addWidget(self.sort_btn)
        self.details = DetailsPanel(mgr)
        self.details.selectRequested.connect(self.reveal)
        self.details.webRequested.connect(self.webRequested)
        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(5)
        split.setChildrenCollapsible(False)
        for w in (self.inactive, self.active, self.details):
            split.addWidget(w)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        split.setSizes([440, 520, 300])
        self.split = split
        root.addWidget(split, 1)

        # === FOOTER ===
        foot = QFrame()
        foot.setObjectName("Footer")
        foot.setFixedHeight(48)
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(12, 0, 12, 0)
        fl.setSpacing(8)
        self.issues_btn = button("", "ghost", icon="warn", icon_color=STATUS["outdated"][1], icon_size=14)
        self.issues_btn.clicked.connect(self._issues_menu)
        self.summary = label("", "dim")
        self.changes = label("", "dim")
        self.revert_btn = button("Revert", "ghost")
        self.revert_btn.clicked.connect(mgr.revert)
        self.apply_btn = button("Apply", "primary", icon="check")
        self.apply_btn.clicked.connect(self.apply)
        self.details_btn = icon_button("panel-right", "Show / hide details", 30, 16, C["text-dim"])
        self.details_btn.clicked.connect(lambda: self.details.setVisible(not self.details.isVisible()))
        for w in (self.issues_btn, self.summary):
            fl.addWidget(w)
        fl.addStretch(1)
        for w in (self.changes, self.revert_btn, self.apply_btn, self.details_btn):
            fl.addWidget(w)
        root.addWidget(foot)

        # === WIRING ===
        for col, other in ((self.inactive, "activate"), (self.active, "deactivate")):
            col.view.toggled.connect(getattr(mgr, other))
            col.view.current.connect(self.details.show_uid)
            col.view.setContextMenuPolicy(Qt.CustomContextMenu)
            col.view.customContextMenuRequested.connect(lambda pos, c=col: self._menu(c, pos))
        mgr.changed.connect(self.refresh)
        mgr.stagedChanged.connect(self.refresh)
        mgr.scanningChanged.connect(self.spinner.setVisible)
        thumbs.ready.connect(lambda _: (self.inactive.view.viewport().update(), self.active.view.viewport().update()))
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.apply, context=Qt.WidgetWithChildrenShortcut)
        self.refresh()

    # === STATE ===
    def refresh(self):
        m = self.mgr
        self.sort_btn.setVisible(m.ordered)
        errors = sum(1 for i in m.issues if i.level == validate.ERROR)
        n = len(m.issues)
        self.issues_btn.setVisible(n > 0)
        self.issues_btn.setText(f"{n} issue{'s' if n != 1 else ''}")
        self.issues_btn.setIcon(icons.icon("warn", STATUS["failed" if errors else "outdated"][1], 14, 2.2))
        installed = len(m.by_uid)
        self.summary.setText(f"{installed} installed · {len(m.staged)} active" + (f" · {m.version}" if m.version else ""))
        ch = m.changes
        self.changes.setText(f"{ch.count} unsaved change{'s' if ch.count != 1 else ''}" if ch.count else "")
        self.revert_btn.setEnabled(ch.count > 0)
        self.apply_btn.setEnabled(ch.count > 0 and not m.apply_block)
        self.banner.setVisible(bool(m.apply_block) and m.app.profile is not None)
        self.banner.setText(m.apply_block)

    def reveal(self, uid):
        """Select uid in whichever column holds it."""
        col = self.active if uid in self.mgr.staged else self.inactive
        if uid not in col.model.rows:
            col.filter.clear()
        col.view.select_uids([uid])
        col.view.setFocus()
        self.details.show_uid(uid)

    # === APPLY ===
    def apply(self):
        m = self.mgr
        if not m.dirty or m.apply_block:
            return
        asks = m.apply_checks()
        if asks:
            box = QMessageBox(self)
            box.setWindowTitle("Apply changes?")
            box.setIcon(QMessageBox.Warning)
            box.setText("\n\n".join(text for _, text in asks))
            go = box.addButton("Apply anyway", QMessageBox.AcceptRole)
            reload = box.addButton("Reload from disk", QMessageBox.DestructiveRole) \
                if any(k == "changed" for k, _ in asks) else None
            box.addButton(QMessageBox.Cancel)
            box.exec()
            if box.clickedButton() is reload:
                m.revert()
                m.refresh()
                return
            if box.clickedButton() is not go:
                return
        m.apply()

    # === MENUS ===
    def _issues_menu(self):
        menu = QMenu(self)
        for issue in self.mgr.issues[:40]:
            color = STATUS["failed" if issue.level == validate.ERROR else "outdated"][1]
            act = menu.addAction(icons.icon("warn", color, 14), f"{self.mgr.title(issue.uid)}: {issue.text}")
            act.triggered.connect(lambda _=False, u=issue.uid: self.reveal(u))
        if len(self.mgr.issues) > 40:
            menu.addAction(f"… {len(self.mgr.issues) - 40} more").setEnabled(False)
        menu.exec(self.issues_btn.mapToGlobal(QPoint(0, 0)) - QPoint(0, menu.sizeHint().height() + 4))

    def _menu(self, col, pos):
        uids = col.view.selected_uids()
        if not uids:
            return
        m = self.mgr
        menu = QMenu(self)
        if col is self.inactive:
            menu.addAction(icons.icon("plus", C["text"], 14), "Activate", lambda: m.activate(uids))
        else:
            menu.addAction(icons.icon("x", C["text"], 14), "Deactivate", lambda: m.deactivate(uids))
            if m.ordered:
                first = next((u for u in m.staged if u not in uids), None)
                menu.addAction("Move to top", lambda: m.activate(uids, first))
                menu.addAction("Move to bottom", lambda: m.activate(uids))
        if len(uids) == 1:
            e = m.by_uid.get(uids[0])
            menu.addSeparator()
            if e and e.path:
                menu.addAction(icons.icon("folder", C["text"], 14), "Open folder", self.details._open_folder)
            if e and e.wid:
                menu.addAction(icons.icon("external", C["text"], 14), "Workshop page",
                               lambda: self.webRequested.emit(ids.workshop_url(e.wid)))
        menu.exec(col.view.viewport().mapToGlobal(pos))
