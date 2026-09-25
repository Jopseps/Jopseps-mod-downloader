"""Right side: nav bar + embedded Steam Workshop. Injected '+ Add' buttons arrive in milestone 3."""
import os

from PySide6.QtCore import QRect, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from jmd import paths
from jmd.core import steam_api
from jmd.ui import icons
from jmd.ui.tokens import C, SIZE
from jmd.ui.widgets import icon_button, label

try:
    if os.environ.get("JMD_NO_WEB"):
        raise ImportError("disabled by JMD_NO_WEB")
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAVE_WEB = True
except ImportError:
    HAVE_WEB = False


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
        url_box = QFrame()
        url_box.setObjectName("UrlBox")
        url_box.setFixedHeight(26)
        ul = QHBoxLayout(url_box)
        ul.setContentsMargins(8, 0, 8, 0)
        ul.setSpacing(6)
        lock = QLabel()
        lock.setPixmap(icons.pixmap("lock", "#6fbf4a", 12))
        self.url_host = QLabel("steamcommunity.com")
        self.url_path = QLabel()
        mono = f"font-family:'JetBrains Mono';font-size:11.5px;background:transparent;"
        self.url_host.setStyleSheet(mono + f"color:{C['text']};")
        self.url_path.setStyleSheet(mono + f"color:{C['text-dim']};")
        ul.addWidget(lock)
        ul.addWidget(self.url_host)
        ul.addSpacing(-6)  # host and path read as one URL
        ul.addWidget(self.url_path, 1)
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
            self.view = QWebEngineView()
            self.view.setPage(QWebEnginePage(profile, self.view))
            self.view.page().setBackgroundColor(QColor(C["panel"]))
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

    def go_home(self):
        p = self.ctl.profile
        url = steam_api.workshop_home(p.app_id) if p else "https://steamcommunity.com/workshop/"
        if self.view:
            self.view.setUrl(QUrl(url))
        else:
            self._url_changed(QUrl(url))

    def _url_changed(self, url):
        self.url_host.setText(url.host() or "steamcommunity.com")
        path = url.path() + (("?" + url.query()) if url.query() else "")
        self.url_path.setText(self.url_path.fontMetrics().elidedText(path, Qt.ElideRight, max(80, self.url_path.width())))
        if self.view:
            hist = self.view.history()
            self.back.setEnabled(hist.canGoBack())
            self.fwd.setEnabled(hist.canGoForward())
