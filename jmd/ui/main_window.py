# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QPushButton, QSplitter, QVBoxLayout, QWidget

from jmd import APP_NAME
from jmd.ui import icons
from jmd.ui.browser_pane import BrowserPane
from jmd.ui.log_panel import LogPanel
from jmd.ui.queue_panel import LeftPanel
from jmd.ui.thumbs import ThumbCache
from jmd.ui.tokens import C, SIZE
from jmd.ui.widgets import Toast, icon_button


class ProfileButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("kind", "profile")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(28)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 8, 0)
        lay.setSpacing(8)
        self.cap = QLabel()
        self.cap.setFixedSize(16, 16)
        self.name = QLabel("No profile")
        self.name.setStyleSheet("font-weight:600;background:transparent;")
        self.appid = QLabel()
        self.appid.setStyleSheet(f"font-family:'JetBrains Mono';font-size:11px;color:{C['text-dim']};background:transparent;")
        chev = QLabel()
        chev.setPixmap(icons.pixmap("chevron-down", C["text"], 14))
        for w in (self.cap, self.name, self.appid, chev):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
            lay.addWidget(w)

    def sizeHint(self):
        return QSize(self.layout().sizeHint().width(), 28)


def square_icon(pixmap, size, fallback):
    if pixmap is None or pixmap.isNull():
        pm = QPixmap(size * 2, size * 2)
        pm.fill(QColor(fallback))
        pm.setDevicePixelRatio(2)
        return pm
    side = min(pixmap.width(), pixmap.height())
    sq = pixmap.copy((pixmap.width() - side) // 2, (pixmap.height() - side) // 2, side, side)
    sq = sq.scaled(size * 2, size * 2, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    sq.setDevicePixelRatio(2)
    return sq


class MainWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.ctl = controller
        self.setWindowTitle(APP_NAME)
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)
        self.thumbs = ThumbCache(80, self)

        central = QWidget()
        central.setObjectName("Window")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # === TOP BAR ===
        top = QFrame()
        top.setObjectName("TopBar")
        top.setFixedHeight(SIZE["topbar"])
        tl = QHBoxLayout(top)
        tl.setContentsMargins(14, 0, 8, 0)
        tl.setSpacing(12)
        word = QLabel(APP_NAME)
        word.setObjectName("Wordmark")
        div = QFrame()
        div.setFixedSize(1, 18)
        div.setStyleSheet(f"background:{C['border']};")
        self.profile_btn = ProfileButton()
        self.profile_btn.clicked.connect(self._profile_menu)
        self.settings_btn = icon_button("settings", "Settings", 30, 16, C["text-dim"])
        self.settings_btn.clicked.connect(self.open_settings)
        tl.addWidget(word)
        tl.addWidget(div)
        tl.addWidget(self.profile_btn)
        tl.addStretch(1)
        tl.addWidget(self.settings_btn)
        root.addWidget(top)

        # === BODY ===
        self.left = LeftPanel(controller, self.thumbs)
        self.left.loginRequested.connect(self.open_login)
        self.browser = BrowserPane(controller)
        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(5)
        split.setChildrenCollapsible(False)
        split.addWidget(self.left)
        split.addWidget(self.browser)
        split.setStretchFactor(1, 1)
        split.setSizes([SIZE["left"], 1440 - SIZE["left"]])
        self.split = split
        root.addWidget(split, 1)
        self.log = LogPanel(controller)
        root.addWidget(self.log)

        self.toast = Toast(central)
        controller.toast.connect(self.toast.show_message)
        controller.profileChanged.connect(self.refresh_profile)
        controller.loginEvent.connect(self._login_event)
        self.thumbs.ready.connect(lambda k: self.refresh_profile() if k.startswith("app_") else None)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.left._save_as)
        self.refresh_profile()
        self._login_dialog = None

    # === PROFILE ===
    def _cap_pixmap(self, profile):
        pm = self.thumbs.get(f"app_{profile.app_id}", profile.capsule_url)
        return square_icon(pm, 16, C["raised"])

    def refresh_profile(self):
        p = self.ctl.profile
        if p:
            self.profile_btn.name.setText(p.name)
            self.profile_btn.appid.setText(str(p.app_id))
            self.profile_btn.cap.setPixmap(self._cap_pixmap(p))
        else:
            self.profile_btn.name.setText("No profile")
            self.profile_btn.appid.setText("")
            self.profile_btn.cap.setPixmap(square_icon(None, 16, C["raised"]))
        self.profile_btn.updateGeometry()

    def _profile_menu(self):
        menu = QMenu(self)
        menu.setMinimumWidth(260)
        check = icons.icon("check", C["accent"], 14, 2.5)
        for p in self.ctl.profiles:
            act = menu.addAction(f"{p.name}\t{p.app_id}", lambda pid=p.id: self.ctl.switch_profile(pid))
            act.setIcon(check if self.ctl.profile and p.id == self.ctl.profile.id else QIcon(self._cap_pixmap(p)))
        if self.ctl.profiles:
            menu.addSeparator()
        menu.addAction(icons.icon("plus", C["text"], 14), "New profile…", self.new_profile)
        menu.exec(self.profile_btn.mapToGlobal(self.profile_btn.rect().bottomLeft()) + QPoint(0, 4))

    # === DIALOGS ===
    def new_profile(self):
        from jmd.ui.dialogs.profile import ProfileDialog
        dlg = ProfileDialog(self.ctl, self.thumbs, self)
        dlg.exec()

    def open_settings(self):
        from jmd.ui.dialogs.settings import SettingsDialog
        SettingsDialog(self.ctl, self.thumbs, self).exec()

    def open_login(self):
        from jmd.ui.dialogs.login import LoginDialog
        if self._login_dialog:
            self._login_dialog.raise_()
            return
        self._login_dialog = LoginDialog(self.ctl, self)
        self._login_dialog.finished.connect(lambda _: setattr(self, "_login_dialog", None))
        self._login_dialog.show()

    def _login_event(self, kind, detail):
        if self._login_dialog:
            self._login_dialog.on_event(kind, detail)

    def open_onboarding(self):
        from jmd.ui.dialogs.onboarding import OnboardingDialog
        OnboardingDialog(self.ctl, self.thumbs, self).exec()

    # === QT ===
    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.toast.isVisible():
            self.toast.reposition()

    def closeEvent(self, e):
        self.ctl.cancel()
        self.ctl._save_queue()
        super().closeEvent(e)
