# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Manage mode: Inactive | Active | Details columns, staged edits, Apply / Revert."""
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox,
                               QPushButton, QSplitter, QVBoxLayout)

from jmd.core import ids, mods, validate
from jmd.ui import icons
from jmd.ui.details_panel import DetailsPanel
from jmd.ui.mod_list import ModDelegate, ModListModel, ModListView
from jmd.ui.tokens import C, SIZE, STATUS
from jmd.ui.widgets import Spinner, button, icon_button, label


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
        self.banner.setTextFormat(Qt.RichText)
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
        self.modset_btn = QPushButton()
        self.modset_btn.setProperty("kind", "select")
        self.modset_btn.setCursor(Qt.PointingHandCursor)
        self.modset_btn.setIcon(icons.icon("list", C["text-dim"], 14))
        self.modset_btn.setToolTip("Modsets: saved active lists")
        self.modset_btn.clicked.connect(self._modset_menu)
        self.active.head.insertWidget(2, self.modset_btn)
        self.active.head.addWidget(self.sort_btn)
        self.details = DetailsPanel(mgr)
        self.details.selectRequested.connect(self.reveal)
        self.details.webRequested.connect(self.webRequested)
        self.details.deleteRequested.connect(self.delete)
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
        self.check_spin = Spinner()
        self.check_btn = button("Check updates", "ghost", icon="refresh", icon_size=13)
        self.check_btn.clicked.connect(mgr.app.check_updates)
        self.update_btn = button("Update all", icon="download", icon_size=13)
        self.update_btn.clicked.connect(mgr.app.update_all)
        self.changes = label("", "dim")
        self.revert_btn = button("Revert", "ghost")
        self.revert_btn.clicked.connect(mgr.revert)
        self.apply_btn = button("Apply", "primary", icon="check")
        self.apply_btn.clicked.connect(self.apply)
        self.details_btn = icon_button("panel-right", "Show / hide details", 30, 16, C["text-dim"])
        self.details_btn.clicked.connect(lambda: self.details.setVisible(not self.details.isVisible()))
        for w in (self.issues_btn, self.summary, self.check_spin, self.check_btn, self.update_btn):
            fl.addWidget(w)
        fl.addStretch(1)
        for w in (self.changes, self.revert_btn, self.apply_btn, self.details_btn):
            fl.addWidget(w)
        root.addWidget(foot)

        # === WIRING ===
        for col, other in ((self.inactive, "activate"), (self.active, "deactivate")):
            col.view.toggled.connect(getattr(mgr, other))
            col.view.deleteRequested.connect(self.delete)
            col.view.current.connect(self.details.show_uid)
            col.view.setContextMenuPolicy(Qt.CustomContextMenu)
            col.view.customContextMenuRequested.connect(lambda pos, c=col: self._menu(c, pos))
        mgr.changed.connect(self.refresh)
        mgr.stagedChanged.connect(self.refresh)
        mgr.scanningChanged.connect(self.spinner.setVisible)
        mgr.modsetChanged.connect(self.refresh)
        app = mgr.app
        for sig in (app.installedChanged, app.runChanged):
            sig.connect(self.refresh)
            sig.connect(lambda *_: (self.inactive.view.viewport().update(), self.active.view.viewport().update()))
        app.checkingChanged.connect(lambda _: self.refresh())
        thumbs.ready.connect(lambda _: (self.inactive.view.viewport().update(), self.active.view.viewport().update()))
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.apply, context=Qt.WidgetWithChildrenShortcut)
        self.refresh()

    # === STATE ===
    def refresh(self):
        m = self.mgr
        self.sort_btn.setVisible(m.ordered)
        name = m.modset or "Modsets"
        self.modset_btn.setText(f" {name}" + (" *" if m.modset and m.dirty else "") + "  ▾")
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
        link = f"<a style='color:{C['steam-blue']};text-decoration:none' href='profile'>Open profile settings</a>"
        self.banner.setText(f"{m.apply_block} &nbsp;{link}")
        app = m.app
        outdated = len(app.outdated())
        updating = len(app.updating)
        self.check_spin.setVisible(app.checking)
        self.check_btn.setVisible(bool(app.installed))
        self.check_btn.setText("Checking…" if app.checking else "Check updates")
        self.check_btn.setEnabled(not app.checking and app.run is None)
        self.update_btn.setVisible(outdated > 0 or updating > 0)
        self.update_btn.setText(f"Updating {updating}…" if updating else f"Update all ({outdated})")
        self.update_btn.setEnabled(outdated > 0 and app.run is None and not app.checking)

    def reveal(self, uid):
        """Select uid in whichever column holds it."""
        col = self.active if uid in self.mgr.staged else self.inactive
        if uid not in col.model.rows:
            col.filter.clear()
        col.view.select_uids([uid])
        col.view.setFocus()
        self.details.show_uid(uid)

    def showEvent(self, e):
        super().showEvent(e)
        self.mgr.auto_check()

    # === DELETE ===
    def delete(self, uids):
        m = self.mgr
        uids = [u for u in uids if m.deletable(u)]
        if not uids:
            m.app.toast.emit("Steam subscriptions and game files can't be deleted here")
            return
        local = [u for u in uids if m.by_uid[u].source != mods.JMM]
        names = ", ".join(m.title(u) for u in uids[:5]) + ("…" if len(uids) > 5 else "")
        text = f"Delete {len(uids)} mod{'s' if len(uids) != 1 else ''} from disk?\n\n{names}"
        if local:
            text += (f"\n\n{len(local)} of them were installed by hand. There's no copy to restore them from: "
                     "this is permanent.")
        else:
            text += "\n\nYou can download them again later."
        box = QMessageBox(self)
        box.setWindowTitle("Delete mods")
        box.setIcon(QMessageBox.Warning)
        box.setText(text)
        go = box.addButton("Delete", QMessageBox.DestructiveRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        if box.clickedButton() is go:
            m.delete(uids)

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
                m.reload()
                return
            if box.clickedButton() is not go:
                return
        m.apply()

    # === MENUS ===
    def _issues_menu(self):
        m = self.mgr
        menu = QMenu(self)
        if any(m.fixable(i) for i in m.issues):
            menu.addAction(icons.icon("check", C["accent"], 14), "Fix all (activate, download missing, sort)", m.fix_all)
            menu.addSeparator()
        for issue in m.issues[:40]:
            color = STATUS["failed" if issue.level == validate.ERROR else "outdated"][1]
            text = f"{m.title(issue.uid)}: {issue.text}"
            fix = m.fixable(issue)
            if fix:
                sub = menu.addMenu(icons.icon("warn", color, 14), text)
                sub.addAction(fix, lambda i=issue: m.fix(i))
                sub.addAction("Show", lambda u=issue.uid: self.reveal(u))
            else:
                menu.addAction(icons.icon("warn", color, 14), text, lambda u=issue.uid: self.reveal(u))
        if len(m.issues) > 40:
            menu.addAction(f"… {len(m.issues) - 40} more").setEnabled(False)
        menu.exec(self.issues_btn.mapToGlobal(QPoint(0, 0)) - QPoint(0, menu.sizeHint().height() + 4))

    def _modset_menu(self):
        m = self.mgr
        if not m.app.profile:
            return
        menu = QMenu(self)
        check = icons.icon("check", C["accent"], 14)
        names = m.modset_names()
        for name in names:
            act = menu.addAction(name, lambda n=name: self._offer_missing(m.load_modset(n)))
            if name == m.modset:
                act.setIcon(check)
        if not names:
            menu.addAction("No saved modsets").setEnabled(False)
        menu.addSeparator()
        if m.modset:
            menu.addAction(f'Save "{m.modset}"', lambda: m.save_modset(m.modset))
        menu.addAction("Save as…", self._save_as)
        menu.addAction("Import…", self._import)
        menu.addAction("Export .txt…", self._export)
        if m.modset:
            menu.addSeparator()
            menu.addAction(icons.icon("trash", C["danger"], 14), f'Delete "{m.modset}"', self._delete)
        menu.exec(self.modset_btn.mapToGlobal(self.modset_btn.rect().bottomLeft()) + QPoint(0, 4))

    def _save_as(self):
        name, ok = QInputDialog.getText(self, "Save modset", "Name:", text=self.mgr.modset)
        if ok and name.strip():
            self.mgr.save_modset(name.strip())

    def _filters(self, pairs):
        return ";;".join(f"{n} ({p})" for n, p in pairs) + ";;All files (*)"

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import modset", "", self._filters(self.mgr.handler.modset_import_filters))
        if path:
            self._offer_missing(self.mgr.import_modset(path))

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export active list", f"{self.mgr.modset or 'modset'}.txt",
                                              "Text list (*.txt)")
        if path:
            self.mgr.export_modset(path)

    def _delete(self):
        name = self.mgr.modset
        if QMessageBox.question(self, "Delete modset", f'Delete "{name}"? Mods on disk are not touched.') == QMessageBox.Yes:
            self.mgr.delete_modset(name)

    def _offer_missing(self, missing):
        if not missing:
            return
        can = [r for r in missing if r.wid]
        names = ", ".join(r.name or r.uid or r.wid for r in missing[:6]) + ("…" if len(missing) > 6 else "")
        if not can:
            QMessageBox.information(self, "Not installed", f"{len(missing)} mods aren't installed and have no "
                                    f"Workshop ID to download: {names}")
            return
        box = QMessageBox(self)
        box.setWindowTitle("Mods not installed")
        box.setIcon(QMessageBox.Question)
        box.setText(f"{len(missing)} mods in this modset aren't installed: {names}\n\n"
                    f"Download {len(can)} of them now? They'll join the active list when they arrive "
                    "(press Apply to save it).")
        go = box.addButton("Download", QMessageBox.AcceptRole)
        box.addButton("Not now", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is go:
            self.mgr.download_missing(can)

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
        if any(m.deletable(u) for u in uids):
            menu.addAction(icons.icon("trash", C["danger"], 14), "Delete…", lambda: self.delete(uids))
        if len(uids) == 1:
            e = m.by_uid.get(uids[0])
            menu.addSeparator()
            if e and e.path:
                menu.addAction(icons.icon("folder", C["text"], 14), "Open folder", self.details._open_folder)
            if e and e.wid:
                menu.addAction(icons.icon("external", C["text"], 14), "Workshop page",
                               lambda: self.webRequested.emit(ids.workshop_url(e.wid)))
        menu.exec(col.view.viewport().mapToGlobal(pos))
