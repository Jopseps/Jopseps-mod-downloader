# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Right side: nav bar with an editable address bar + embedded Steam Workshop with injected '+ Add' buttons."""
import os

from PySide6.QtCore import QRect, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QStackedLayout, QVBoxLayout, QWidget

from jmd import paths
from jmd.core import ids, steam_api
from jmd.ui import icons
from jmd.ui.tokens import C, SIZE
from jmd.ui.widgets import icon_button, label, restyle

try:
    if os.environ.get("JMD_NO_WEB"):
        raise ImportError("disabled by JMD_NO_WEB")
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineScript
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAVE_WEB = True
except ImportError:
    HAVE_WEB = False

if HAVE_WEB:
    class WebView(QWebEngineView):
        def createWindow(self, _type):
            """target=_blank / window.open: load in this view instead of dropping the request."""
            return self


class LoadBar(QWidget):
    """2px Steam-blue line under the nav bar while a page loads."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(2)
        self.pct = 0

    def set_pct(self, pct):
        self.pct = pct
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(C["bg"]))
        if 0 < self.pct < 100:
            p.fillRect(QRect(0, 0, int(self.width() * self.pct / 100), 2), QColor(C["steam-blue"]))


class UrlEdit(QLineEdit):
    """Address field shown while editing. Enter submits, Esc or focus loss cancels."""
    submitted = Signal(str)
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("UrlEdit")
        self._done = False

    def start(self, text):
        self._done = False
        self.setText(text)
        self.setFocus(Qt.ShortcutFocusReason)
        self.selectAll()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._done = True
            self.submitted.emit(self.text())
        elif e.key() == Qt.Key_Escape:
            self._done = True
            self.cancelled.emit()
        else:
            super().keyPressEvent(e)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        if not self._done:
            self._done = True
            self.cancelled.emit()


class UrlBox(QFrame):
    """Two-tone host/path display; a click swaps in the editable field."""
    clicked = Signal()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)


class BrowserPane(QFrame):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.ctl = controller
        self.setStyleSheet(f"BrowserPane{{background:{C['bg']};}}")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # === NAV BAR ===
        nav = QFrame()
        nav.setObjectName("NavBar")
        nav.setFixedHeight(SIZE["navbar"])
        nl = QHBoxLayout(nav)
        nl.setContentsMargins(8, 0, 8, 0)
        nl.setSpacing(2)
        self.back = icon_button("back", "Back")
        self.fwd = icon_button("forward", "Forward")
        self.home = icon_button("home", "Home")
        self.reload = icon_button("refresh", "Reload", icon_size=15)
        for b in (self.back, self.fwd, self.home, self.reload):
            nl.addWidget(b)
        url_box = self.url_box = UrlBox()
        url_box.setObjectName("UrlBox")
        url_box.setFixedHeight(26)
        url_box.setCursor(Qt.IBeamCursor)
        ul = QHBoxLayout(url_box)
        ul.setContentsMargins(8, 0, 8, 0)
        ul.setSpacing(6)
        self.lock = QLabel()
        self.lock.setPixmap(icons.pixmap("lock", "#6fbf4a", 12))
        # page 0: host + path in two tones, page 1: the editable field
        shown = QWidget()
        sl = QHBoxLayout(shown)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)
        self.url_host = QLabel("steamcommunity.com")
        self.url_path = QLabel()
        mono = f"font-family:'JetBrains Mono';font-size:11.5px;background:transparent;"
        self.url_host.setStyleSheet(mono + f"color:{C['text']};")
        self.url_path.setStyleSheet(mono + f"color:{C['text-dim']};")
        sl.addWidget(self.url_host)
        sl.addWidget(self.url_path, 1)
        self.url_edit = UrlEdit()
        self.url_stack = QStackedLayout()
        self.url_stack.addWidget(shown)
        self.url_stack.addWidget(self.url_edit)
        ul.addWidget(self.lock)
        ul.addLayout(self.url_stack, 1)
        url_box.clicked.connect(self.edit_url)
        self.url_edit.submitted.connect(self._submit_url)
        self.url_edit.cancelled.connect(lambda: self._set_editing(False))
        self.url = QUrl()
        for keys in ("Ctrl+L", "F6"):
            QShortcut(QKeySequence(keys), self, activated=self.edit_url, context=Qt.WindowShortcut)
        nl.addSpacing(6)
        nl.addWidget(url_box, 1)
        root.addWidget(nav)
        self.load_bar = LoadBar()
        root.addWidget(self.load_bar)

        # === CONTENT ===
        if HAVE_WEB:
            # parented to the app so it outlives the page on shutdown
            profile = QWebEngineProfile("jmod", QApplication.instance())
            profile.setPersistentStoragePath(paths.ensure(os.path.join(paths.data_dir(), "web")))
            profile.setCachePath(paths.ensure(os.path.join(paths.data_dir(), "web-cache")))
            profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
            self.view = WebView()
            self.view.setPage(QWebEnginePage(profile, self.view))
            self.view.page().setBackgroundColor(QColor(C["panel"]))
            self._install_injector(self.view.page())
            self.view.urlChanged.connect(self._url_changed)
            self.view.loadProgress.connect(self.load_bar.set_pct)
            self.view.loadFinished.connect(lambda _: self.load_bar.set_pct(100))
            self.back.clicked.connect(self.view.back)
            self.fwd.clicked.connect(self.view.forward)
            self.reload.clicked.connect(self.view.reload)
            root.addWidget(self.view, 1)
        else:
            self.view = None
            holder = QFrame()
            holder.setStyleSheet(f"background:{C['panel']};")
            hl = QVBoxLayout(holder)
            msg = label("Steam Workshop", "strong")
            msg.setAlignment(Qt.AlignCenter)
            sub = label("Embedded browser unavailable (QtWebEngine not loaded).", "dim")
            sub.setAlignment(Qt.AlignCenter)
            hl.addStretch(1)
            hl.addWidget(msg)
            hl.addWidget(sub)
            hl.addStretch(1)
            root.addWidget(holder, 1)
        self.home.clicked.connect(self.go_home)
        controller.profileChanged.connect(self.go_home)
        QTimer.singleShot(0, self.go_home)

    def _install_injector(self, page):
        """'+ Add' pills: qwebchannel.js + inject.js in an isolated world, bridged to the controller."""
        from jmd.ui.web_bridge import WorkshopBridge, script_source
        self.bridge = WorkshopBridge(self.ctl, self)
        channel = QWebChannel(page)
        channel.registerObject("jmd", self.bridge)
        page.setWebChannel(channel, QWebEngineScript.ApplicationWorld)
        script = QWebEngineScript()
        script.setName("jmd-inject")
        script.setSourceCode(script_source())
        script.setInjectionPoint(QWebEngineScript.DocumentReady)
        script.setWorldId(QWebEngineScript.ApplicationWorld)
        script.setRunsOnSubFrames(False)
        page.scripts().insert(script)

    def go_home(self):
        p = self.ctl.profile
        url = steam_api.workshop_home(p.app_id) if p else "https://steamcommunity.com/workshop/"
        if self.view:
            self.view.setUrl(QUrl(url))
        else:
            self._url_changed(QUrl(url))

    # === ADDRESS BAR ===
    def edit_url(self):
        if self.url_stack.currentIndex() == 1:
            return
        self._set_editing(True)
        self.url_edit.start(self.url.toString())

    def _set_editing(self, on):
        self.url_stack.setCurrentIndex(1 if on else 0)
        self.url_box.setProperty("editing", on)
        restyle(self.url_box)

    def _submit_url(self, text):
        self._set_editing(False)
        p = self.ctl.profile
        target = ids.resolve_address(text, p.app_id if p else 0)
        if not target:
            return
        if self.view:
            self.view.setUrl(QUrl(target))
            self.view.setFocus()
        else:
            self._url_changed(QUrl(target))

    def _url_changed(self, url):
        self.url = url
        self.lock.setVisible(url.scheme() == "https")
        self.url_host.setText(url.host() or url.toString())
        path = (url.path() + (("?" + url.query()) if url.query() else "")) if url.host() else ""
        self.url_path.setText(self.url_path.fontMetrics().elidedText(path, Qt.ElideRight, max(80, self.url_path.width())))
        if self.view:
            hist = self.view.history()
            self.back.setEnabled(hist.canGoBack())
            self.fwd.setEnabled(hist.canGoForward())
