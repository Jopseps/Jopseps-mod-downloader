# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
import os

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QListView, QMenu,
                               QPlainTextEdit, QPushButton, QStackedLayout, QStackedWidget, QVBoxLayout, QWidget)

from jmd.core import models
from jmd.core.ids import extract_ids
from jmd.ui import icons
from jmd.ui.delegates import InstalledDelegate, QueueDelegate
from jmd.ui.queue_model import InstalledModel, QueueModel
from jmd.ui.tokens import C, SIZE, STATUS
from jmd.ui.widgets import Spinner, button, hbox, label, restyle


class PasteBox(QPlainTextEdit):
    """IDs are added the moment they're pasted; Enter adds typed IDs."""
    submitted = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Paste")
        self.setPlaceholderText("Paste Workshop IDs or URLs")
        self.setFixedHeight(48)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def insertFromMimeData(self, source):
        ids = extract_ids(source.text())
        if ids:
            self.clear()
            self.submitted.emit(ids)
        else:
            super().insertFromMimeData(source)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not event.modifiers() & Qt.ShiftModifier:
            ids = extract_ids(self.toPlainText())
            if ids:
                self.clear()
                self.submitted.emit(ids)
            return
        super().keyPressEvent(event)


class TabButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setProperty("kind", "tab")
        self.setCursor(Qt.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(6)
        self.text_label = QLabel(text)
        self.badge = label("0", "badge")
        self.warn = label("", "badge-warn")
        for w in (self.text_label, self.badge, self.warn):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
            lay.addWidget(w)
        self.warn.hide()
        self.set_active(False)

    def set_active(self, on):
        self.setProperty("active", "true" if on else "false")
        color = C["text-strong"] if on else C["text-dim"]
        self.text_label.setStyleSheet(f"color:{color};font-weight:600;background:transparent;")
        restyle(self)

    def sizeHint(self):
        return QSize(self.layout().sizeHint().width(), SIZE["tabs"] - 2)


class ListSelect(QPushButton):
    """'≡ List: Current ▾' dropdown (design: Dropdown · combo box)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("kind", "select")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(28)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(6)
        ic = QLabel()
        ic.setPixmap(icons.pixmap("list", C["text-dim"], 14))
        pre = label("List:")
        pre.setStyleSheet(f"color:{C['text-dim']};font-weight:400;background:transparent;")
        self.name = QLabel("Current")
        self.name.setStyleSheet("font-weight:600;background:transparent;")
        chev = QLabel()
        chev.setPixmap(icons.pixmap("chevron-down", C["text"], 14))
        for w in (ic, pre, self.name):
            lay.addWidget(w)
        lay.addStretch(1)
        lay.addWidget(chev)
        for w in (ic, pre, self.name, chev):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)


class RunBox(QFrame):
    """Footer while downloading: spinner + 'Downloading 4/12…' + 2px progress line along the bottom."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RunBox")
        self.setFixedHeight(34)
        self.pct = 0.0
        lay = hbox(Spinner(), spacing=8, margins=(12, 0, 12, 0))
        self.text = QLabel()
        self.text.setStyleSheet(f"color:{C['text-strong']};font-weight:600;background:transparent;")
        lay.addWidget(self.text)
        lay.addStretch(1)
        self.setLayout(lay)

    def set_progress(self, text, pct):
        self.text.setText(text)
        self.pct = pct
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.fillRect(QRect(1, self.height() - 3, int((self.width() - 2) * self.pct / 100), 2), QColor(C["steam-blue"]))


def _list_view(delegate, model):
    view = QListView()
    view.setModel(model)
    view.setItemDelegate(delegate)
    delegate.setParent(view)
    view.setMouseTracking(True)
    view.setSelectionMode(QListView.NoSelection)
    view.setVerticalScrollMode(QListView.ScrollPerPixel)
    view.setFrameShape(QFrame.NoFrame)
    view.setFocusPolicy(Qt.NoFocus)
    view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    view.setResizeMode(QListView.Adjust)
    return view


class LeftPanel(QFrame):
    loginRequested = Signal()

    def __init__(self, controller, thumbs, parent=None):
        super().__init__(parent)
        self.ctl = controller
        self.thumbs = thumbs
        self.setObjectName("LeftPanel")
        self.setMinimumWidth(SIZE["left-min"])
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # === TABS ===
        tabs = QFrame()
        tabs.setObjectName("TabBar")
        tabs.setFixedHeight(SIZE["tabs"])
        tl = QHBoxLayout(tabs)
        tl.setContentsMargins(8, 0, 8, 0)
        tl.setSpacing(4)
        self.tab_queue = TabButton("Queue")
        self.tab_inst = TabButton("Installed")
        tl.addWidget(self.tab_queue)
        tl.addWidget(self.tab_inst)
        tl.addStretch(1)
        root.addWidget(tabs)
        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)
        self.pages.addWidget(self._build_queue_page())
        self.pages.addWidget(self._build_installed_page())
        self.tab_queue.clicked.connect(lambda: self.show_tab(0))
        self.tab_inst.clicked.connect(lambda: self.show_tab(1))
        self.show_tab(0)

        # === WIRING ===
        c = controller
        c.queueChanged.connect(self.refresh)
        c.itemChanged.connect(lambda _: self.refresh_counts())
        c.runChanged.connect(self.refresh_footer)
        c.installedChanged.connect(self.refresh_installed)
        c.checkingChanged.connect(lambda _: self.refresh_installed())
        c.listChanged.connect(self.list_select.name.setText)
        c.profileChanged.connect(self.refresh_installed)
        thumbs.ready.connect(lambda _: (self.queue_view.viewport().update(), self.inst_view.viewport().update()))
        self._spin = QTimer(self)
        self._spin.timeout.connect(self._tick)
        self._spin.start(33)
        self.refresh()
        self.refresh_installed()

    # === QUEUE PAGE ===
    def _build_queue_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        top = QFrame()
        top.setObjectName("QueueTop")
        tl = QVBoxLayout(top)
        tl.setContentsMargins(10, 10, 10, 10)
        tl.setSpacing(8)
        self.list_select = ListSelect()
        self.list_select.clicked.connect(self._list_menu)
        self.paste = PasteBox()
        self.paste.submitted.connect(self.ctl.add_ids)
        tl.addWidget(self.list_select)
        tl.addWidget(self.paste)
        lay.addWidget(top)

        frame = QFrame()
        frame.setObjectName("TreeFrame")
        stack = QStackedLayout(frame)
        self.queue_model = QueueModel(self.ctl, self)
        self.queue_delegate = QueueDelegate(self.ctl, self.thumbs)
        self.queue_delegate.loginRequested.connect(self.loginRequested)
        self.queue_view = _list_view(self.queue_delegate, self.queue_model)
        empty = QWidget()
        el = QVBoxLayout(empty)
        el.setContentsMargins(24, 40, 24, 24)
        head = label("Queue is empty", "strong")
        head.setAlignment(Qt.AlignHCenter)
        hint = QLabel(f'Click <span style="color:{C["accent"]};font-weight:600">+ Add</span> on a Workshop page, '
                      f'or paste IDs above.')
        hint.setAlignment(Qt.AlignHCenter)
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{C['text-dim']};")
        el.addWidget(head)
        el.addWidget(hint)
        el.addStretch(1)
        stack.addWidget(self.queue_view)
        stack.addWidget(empty)
        self.queue_stack = stack
        lay.addWidget(frame, 1)

        footer = QFrame()
        footer.setObjectName("Footer")
        footer.setMinimumHeight(56)
        self.footer_stack = QStackedLayout(footer)
        idle = QWidget()
        il = QHBoxLayout(idle)
        il.setContentsMargins(10, 10, 10, 10)
        il.setSpacing(10)
        self.dl_btn = button("Download", "primary", "lg", icon="download")
        self.dl_btn.clicked.connect(lambda: self.ctl.download())
        il.addWidget(self.dl_btn)
        summary = QHBoxLayout()
        summary.setSpacing(8)
        self.failed_lbl = QLabel()
        self.failed_lbl.setStyleSheet(f"color:{STATUS['failed'][1]};font-size:12px;")
        self.retry_btn = QPushButton("Retry failed")
        self.retry_btn.setProperty("kind", "link")
        self.retry_btn.setStyleSheet(f"color:{C['text']};text-decoration:underline;")
        self.retry_btn.setCursor(Qt.PointingHandCursor)
        self.retry_btn.clicked.connect(self.ctl.retry_failed)
        self.login_btn = QPushButton()
        self.login_btn.setProperty("kind", "link")
        self.login_btn.setStyleSheet(f"color:{STATUS['login'][1]};")
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.clicked.connect(self.loginRequested)
        self.done_lbl = label("", "dim")
        for w in (self.failed_lbl, self.retry_btn, self.login_btn, self.done_lbl):
            summary.addWidget(w)
        summary.addStretch(1)
        il.addLayout(summary, 1)
        running = QWidget()
        rl = QHBoxLayout(running)
        rl.setContentsMargins(10, 10, 10, 10)
        rl.setSpacing(10)
        self.run_box = RunBox()
        cancel = button("Cancel", size="lg")
        cancel.clicked.connect(self.ctl.cancel)
        rl.addWidget(self.run_box, 1)
        rl.addWidget(cancel)
        self.footer_stack.addWidget(idle)
        self.footer_stack.addWidget(running)
        lay.addWidget(footer)
        return page

    def _list_menu(self):
        menu = QMenu(self)
        menu.addAction("Save as…\tCtrl+S", self._save_as)
        load = menu.addMenu("Load")
        names = self.ctl.list_names() if self.ctl.profile else []
        for name in names:
            load.addAction(name, lambda n=name: self.ctl.load_list(n))
        load.setEnabled(bool(names))
        menu.addSeparator()
        menu.addAction("Import…", self._import)
        menu.addAction("Export…", self._export)
        menu.addSeparator()
        menu.addAction("Delete", self.ctl.delete_list)
        for a in menu.actions():
            a.setEnabled(a.isEnabled() and self.ctl.profile is not None)
        menu.setFixedWidth(self.list_select.width())
        menu.exec(self.list_select.mapToGlobal(self.list_select.rect().bottomLeft()) + QPoint(0, 4))

    def _save_as(self):
        name, ok = QInputDialog.getText(self, "Save list", "List name:",
                                        text="" if self.ctl.list_name == "Current" else self.ctl.list_name)
        if ok and name.strip():
            self.ctl.save_list_as(name.strip())

    def _filters(self, pairs):
        return ";;".join(f"{name} ({pattern})" for name, pattern in pairs + [("All files", "*")])

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import mod list", "", self._filters(self.ctl.handler.import_filters))
        if path:
            self.ctl.import_file(path)

    def _export(self):
        default = f"{self.ctl.profile.name.lower().replace(' ', '')}_list.txt"
        path, _ = QFileDialog.getSaveFileName(self, "Export mod list", default,
                                              self._filters(self.ctl.handler.export_filters))
        if path:
            self.ctl.export_file(path)

    # === INSTALLED PAGE ===
    def _build_installed_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        head = QFrame()
        head.setObjectName("InstHeader")
        head.setFixedHeight(40)
        hl = QHBoxLayout(head)
        hl.setContentsMargins(12, 0, 12, 0)
        hl.setSpacing(8)
        self.inst_spin = Spinner()
        self.inst_summary = label("", "dim")
        self.sync_lbl = label("", "monodim")
        self.sync_lbl.setStyleSheet(f"color:{C['text-faint']};")
        self.sync_lbl.setMaximumWidth(150)
        hl.addWidget(self.inst_spin)
        hl.addWidget(self.inst_summary)
        hl.addStretch(1)
        hl.addWidget(self.sync_lbl)
        lay.addWidget(head)
        self.inst_model = InstalledModel(self.ctl, self)
        self.inst_view = _list_view(InstalledDelegate(self.ctl, self.thumbs), self.inst_model)
        lay.addWidget(self.inst_view, 1)
        footer = QFrame()
        footer.setObjectName("Footer")
        footer.setMinimumHeight(56)
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(10, 10, 10, 10)
        fl.setSpacing(8)
        self.check_btn = button("Check updates", size="lg", icon="refresh", icon_size=14)
        self.check_btn.clicked.connect(self.ctl.check_updates)
        self.update_btn = button("Update all (0)", "primary", "lg")
        self.update_btn.clicked.connect(self.ctl.update_all)
        fl.addWidget(self.check_btn)
        fl.addWidget(self.update_btn)
        fl.addStretch(1)
        lay.addWidget(footer)
        return page

    # === STATE ===
    def show_tab(self, i):
        self.pages.setCurrentIndex(i)
        self.tab_queue.set_active(i == 0)
        self.tab_inst.set_active(i == 1)

    def refresh(self):
        self.queue_stack.setCurrentIndex(0 if self.ctl.queue.nodes else 1)
        self.refresh_counts()

    def refresh_counts(self):
        items = self.ctl.queue.items()
        self.tab_queue.badge.setText(str(len(items)))
        self.refresh_footer()

    def refresh_footer(self):
        run = self.ctl.run
        if run and run["kind"] != "update":
            done, total, pct = self.ctl.run_progress()
            verb = "Logging in" if run["kind"] == "login" and done == 0 else "Downloading"
            self.run_box.set_progress(f"{verb} {done}/{total}…", pct)
            self.footer_stack.setCurrentIndex(1)
            return
        self.footer_stack.setCurrentIndex(0)
        q = self.ctl.queue
        n = len([i for i in q.pending() if i.status != models.LOGIN])
        self.dl_btn.setText(f"Download ({n})" if n else "Download")
        self.dl_btn.setEnabled(n > 0 and run is None)
        failed = sum(1 for i in q.items() if i.status == models.FAILED and i.checked and not i.blocked)
        login = q.count(models.LOGIN)
        done = q.count(models.DONE)
        self.failed_lbl.setText(f"{failed} failed")
        self.failed_lbl.setVisible(failed > 0)
        self.retry_btn.setVisible(failed > 0)
        self.login_btn.setText(f"{login} need login")
        self.login_btn.setVisible(login > 0)
        self.done_lbl.setText(f"{done} done")
        self.done_lbl.setVisible(done > 0 and not failed and not login)

    def refresh_installed(self):
        c = self.ctl
        recs = list(c.installed.values())
        outdated = len(c.outdated())
        updating = len(c.updating)
        self.tab_inst.badge.setText(str(len(recs)))
        self.tab_inst.warn.setText(str(outdated))
        self.tab_inst.warn.setVisible(outdated > 0)
        self.inst_spin.setVisible(c.checking)
        if c.checking:
            self.inst_summary.setText(f"Checking {len(recs)} mods…")
            self.inst_summary.setStyleSheet(f"color:{C['text']};font-size:12px;")
        else:
            self.inst_summary.setStyleSheet("")
            if updating:
                self.inst_summary.setText(f"Updating {updating}…")
            elif outdated:
                self.inst_summary.setText(f"{len(recs)} installed · {outdated} outdated")
            else:
                self.inst_summary.setText(f"{len(recs)} installed · all synced")
        p = c.profile
        if p:
            mode = "Link → " if p.sync_mode == "link" else "Copy → "
            text = mode + (p.mod_dir.replace(os.path.expanduser("~"), "~") if p.mod_dir else "SteamCMD folder")
            self.sync_lbl.setText(self.sync_lbl.fontMetrics().elidedText(text, Qt.ElideMiddle, 150))
            self.sync_lbl.setToolTip(text)
        self.check_btn.setText("Checking…" if c.checking else "Check updates")
        self.check_btn.setEnabled(not c.checking and bool(recs) and c.run is None)
        busy = c.checking or c.run is not None
        if updating:
            self.update_btn.setText(f"Updating {updating}…")
        else:
            self.update_btn.setText(f"Update all ({outdated})")
        self.update_btn.setEnabled(outdated > 0 and not busy)

    def _tick(self):
        rows = self.queue_model.rows
        if not rows or self.pages.currentIndex() != 0:
            return
        top = self.queue_view.indexAt(self.queue_view.viewport().rect().topLeft()).row()
        top = max(0, top)
        visible = rows[top:top + 20]
        if any(getattr(n, "status", None) == models.RESOLVING for n, _ in visible):
            self.queue_delegate.angle = (self.queue_delegate.angle + 15) % 360
            self.queue_view.viewport().update()
