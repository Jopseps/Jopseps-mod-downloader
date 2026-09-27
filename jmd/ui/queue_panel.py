# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel, QListView, QMenu,
                               QPlainTextEdit, QPushButton, QStackedLayout, QVBoxLayout, QWidget)

from jmd.core import models
from jmd.core.ids import extract_ids
from jmd.ui import icons
from jmd.ui.delegates import QueueDelegate
from jmd.ui.queue_model import QueueModel
from jmd.ui.tokens import C, SIZE, STATUS
from jmd.ui.widgets import Spinner, button, hbox, label


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


class ListSelect(QPushButton):
    """'≡ Queue ▾' dropdown: import / export / clear. Named lists live in Manage as modsets."""

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
        pre = label("List file")
        pre.setStyleSheet("font-weight:600;background:transparent;")
        self.name = QLabel("import · export · clear queue")
        self.name.setStyleSheet(f"color:{C['text-faint']};font-weight:400;background:transparent;")
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

        # === HEADER ===
        head = QFrame()
        head.setObjectName("TabBar")
        head.setFixedHeight(SIZE["tabs"])
        hl = QHBoxLayout(head)
        hl.setContentsMargins(14, 0, 12, 0)
        hl.setSpacing(8)
        hl.addWidget(label("Queue", "strong"))
        self.count = label("0", "badge")
        hl.addWidget(self.count)
        hl.addStretch(1)
        root.addWidget(head)
        root.addWidget(self._build_queue_page(), 1)

        # === WIRING ===
        c = controller
        c.queueChanged.connect(self.refresh)
        c.itemChanged.connect(lambda _: self.refresh_counts())
        c.runChanged.connect(self.refresh_footer)
        thumbs.ready.connect(lambda _: self.queue_view.viewport().update())
        self._spin = QTimer(self)
        self._spin.timeout.connect(self._tick)
        self._spin.start(33)
        self.refresh()

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
        menu.addAction("Import list…", self._import)
        menu.addAction("Export queue…", self._export)
        menu.addSeparator()
        menu.addAction("Clear queue", self.ctl.clear_queue)
        for a in menu.actions():
            a.setEnabled(a.isEnabled() and self.ctl.profile is not None)
        menu.setFixedWidth(self.list_select.width())
        menu.exec(self.list_select.mapToGlobal(self.list_select.rect().bottomLeft()) + QPoint(0, 4))

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

    # === STATE ===
    def refresh(self):
        self.queue_stack.setCurrentIndex(0 if self.ctl.queue.nodes else 1)
        self.refresh_counts()

    def refresh_counts(self):
        items = self.ctl.queue.items()
        self.count.setText(str(len(items)))
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

    def _tick(self):
        rows = self.queue_model.rows
        if not rows:
            return
        top = self.queue_view.indexAt(self.queue_view.viewport().rect().topLeft()).row()
        top = max(0, top)
        visible = rows[top:top + 20]
        if any(getattr(n, "status", None) == models.RESOLVING for n, _ in visible):
            self.queue_delegate.angle = (self.queue_delegate.angle + 15) % 360
            self.queue_view.viewport().update()
