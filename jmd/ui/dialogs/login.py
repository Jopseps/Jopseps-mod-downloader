# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Steam login mid-download: credentials → Steam Guard code / mobile approval → success.
Prompt strings from SteamCMD are unverified without a test account; see core/steamcmd.py PROMPTS."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QStackedWidget, QVBoxLayout, QWidget

from jmd.ui import icons
from jmd.ui.tokens import C, STATUS
from jmd.ui.widgets import Dialog, Spinner, button, label


class LoginDialog(Dialog):
    def __init__(self, controller, parent=None):
        super().__init__("Steam login", 400, parent)
        self.ctl = controller
        self.step = "creds"
        self.busy = False
        self.resume_n = len(controller.login_items())
        self.stack = QStackedWidget()
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.addWidget(self.stack)

        # === CREDENTIALS ===
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(16, 16, 16, 16)
        l.setSpacing(12)
        name = controller.profile.name if controller.profile else "This game"
        n = self.resume_n
        l.addWidget(label(f"{name} needs an account that owns it to download {n} item{'s' if n != 1 else ''}. "
                          f"Other downloads keep running.", wrap=True))
        self.err = QLabel()
        self.err.setObjectName("ErrBanner")
        self.err.setWordWrap(True)
        self.err.setStyleSheet("padding:8px 10px;font-size:12px;")
        self.err.hide()
        l.addWidget(self.err)
        self.user = QLineEdit(controller.settings.username)
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.Password)
        self.pw.returnPressed.connect(self._action)
        for title, field in (("Username", self.user), ("Password", self.pw)):
            col = QVBoxLayout()
            col.setSpacing(4)
            t = label(title)
            t.setStyleSheet(f"color:{C['text-dim']};font-size:12px;font-weight:500;")
            col.addWidget(t)
            col.addWidget(field)
            l.addLayout(col)
        l.addWidget(label("Sent to SteamCMD only. The password is never stored.", "faint"))
        self.stack.addWidget(w)

        # === GUARD ===
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(16, 16, 16, 16)
        l.setSpacing(12)
        l.addWidget(label("Steam Guard", "strong"))
        l.addWidget(label("Enter the 5-character code from your email or the Steam Mobile app.", wrap=True))
        self.code = QLineEdit()
        self.code.setObjectName("GuardCode")
        self.code.setMaxLength(5)
        self.code.setAlignment(Qt.AlignCenter)
        self.code.setPlaceholderText("•••••")
        self.code.textChanged.connect(self._code_changed)
        self.code.returnPressed.connect(self._action)
        l.addWidget(self.code)
        self.code_err = QLabel()
        self.code_err.setStyleSheet(f"color:{C['danger']};font-size:12px;")
        self.code_err.hide()
        l.addWidget(self.code_err)
        mobile = button("Approve on Steam Mobile instead", "link")
        mobile.clicked.connect(lambda: self._go("mobile"))
        l.addWidget(mobile, 0, Qt.AlignLeft)
        self.stack.addWidget(w)

        # === MOBILE ===
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(16, 28, 16, 28)
        l.setSpacing(12)
        l.setAlignment(Qt.AlignHCenter)
        l.addWidget(Spinner(28, 3), 0, Qt.AlignHCenter)
        t = label("Approve on Steam Mobile app…", "strong")
        t.setAlignment(Qt.AlignCenter)
        l.addWidget(t)
        self.mobile_text = label("", "dim", wrap=True)
        self.mobile_text.setAlignment(Qt.AlignCenter)
        self.mobile_text.setMaximumWidth(280)
        l.addWidget(self.mobile_text, 0, Qt.AlignHCenter)
        use_code = button("Enter a code instead", "link")
        use_code.clicked.connect(lambda: self._go("guard"))
        l.addWidget(use_code, 0, Qt.AlignHCenter)
        self.stack.addWidget(w)

        # === SUCCESS ===
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(16, 28, 16, 28)
        l.setSpacing(10)
        badge = QLabel()
        badge.setFixedSize(40, 40)
        badge.setAlignment(Qt.AlignCenter)
        badge.setPixmap(icons.pixmap("check", STATUS["done"][1], 20, 2.5))
        badge.setStyleSheet(f"background:{STATUS['done'][2]};border:1px solid {STATUS['done'][3]};border-radius:20px;")
        l.addWidget(badge, 0, Qt.AlignHCenter)
        self.ok_title = label("", "strong")
        self.ok_title.setAlignment(Qt.AlignCenter)
        self.ok_sub = label("", "dim")
        self.ok_sub.setAlignment(Qt.AlignCenter)
        l.addWidget(self.ok_title)
        l.addWidget(self.ok_sub)
        self.stack.addWidget(w)

        # === FOOTER ===
        self.back = button("Back", "ghost")
        self.back.clicked.connect(lambda: self._go("creds"))
        self.cancel = button("Cancel")
        self.cancel.clicked.connect(self._cancel)
        self.busy_btn = button("Logging in…")
        self.busy_btn.setEnabled(False)
        busy_lay = QHBoxLayout(self.busy_btn)
        busy_lay.setContentsMargins(12, 0, 0, 0)
        busy_lay.addWidget(Spinner())
        busy_lay.addStretch(1)
        self.busy_btn.setStyleSheet("padding-left:30px;")
        self.action = button("Log in", "primary")
        self.action.clicked.connect(self._action)
        self.footer_layout.addWidget(self.back)
        self.footer_layout.addStretch(1)
        for b in (self.cancel, self.busy_btn, self.action):
            self.footer_layout.addWidget(b)
        self.user.textChanged.connect(self._refresh)
        self.pw.textChanged.connect(self._refresh)
        self._go("creds")

    def _code_changed(self, text):
        if text != text.upper():
            self.code.setText(text.upper())
            return
        self._refresh()

    # === FLOW ===
    def _go(self, step):
        self.step = step
        self.stack.setCurrentIndex(["creds", "guard", "mobile", "success"].index(step))
        self.mobile_text.setText(f"Open Steam on your phone and approve the sign-in for {self.user.text()}.")
        self._refresh()
        if step == "guard":
            QTimer.singleShot(0, self.code.setFocus)
        elif step == "creds":
            QTimer.singleShot(0, (self.pw if self.user.text() else self.user).setFocus)

    def _refresh(self):
        s = self.step
        self.back.setVisible(s in ("guard", "mobile") and not self.busy)
        self.cancel.setVisible(s != "success")
        self.busy_btn.setVisible(self.busy and s in ("creds", "guard"))
        self.busy_btn.setText("Logging in…" if s == "creds" else "Checking…")
        self.action.setVisible(not self.busy and s != "mobile")
        self.action.setText({"creds": "Log in", "guard": "Submit"}.get(s, "Done"))
        if s == "creds":
            self.action.setEnabled(bool(self.user.text().strip()))
        elif s == "guard":
            self.action.setEnabled(len(self.code.text().strip()) == 5)
        else:
            self.action.setEnabled(True)

    def _action(self):
        if not self.action.isVisible() or not self.action.isEnabled():
            return
        if self.step == "creds":
            self.err.hide()
            self.busy = True
            self._refresh()
            # empty password = reuse SteamCMD's cached session for this user
            self.ctl.login(self.user.text().strip(), self.pw.text())
            self.pw.clear()
        elif self.step == "guard":
            self.code_err.hide()
            self.busy = True
            self._refresh()
            self.ctl.answer_prompt(self.code.text().strip())
        else:
            self.accept()

    def _cancel(self):
        if self.busy and self.ctl.run and self.ctl.run["kind"] == "login":
            self.ctl.cancel()
        self.reject()

    def on_event(self, kind, detail):
        """Controller login events: prompt:<kind>, failed, ok, done."""
        if kind in ("prompt:guard", "prompt:twofactor"):
            self.busy = False
            self.code.clear()
            self._go("guard")
        elif kind == "prompt:mobile":
            self.busy = False
            self._go("mobile")
        elif kind == "prompt:password":
            self.busy = False
            self._show_error("SteamCMD asked for a password. Enter it and try again.")
        elif kind == "failed":
            self.busy = False
            if self.step == "guard" or "code" in detail.lower():
                self.code_err.setText("That code didn't work. Check it and try again.")
                self.code_err.show()
                self._go("guard")
            else:
                self._show_error("Wrong username or password." if "Password" in detail else f"Login failed: {detail}")
        elif kind == "ok" and self.step != "success":
            self.busy = False
            self.ok_title.setText(f"Logged in as {self.user.text()}")
            n = self.resume_n
            self.ok_sub.setText(f"Resuming {n} download{'s' if n != 1 else ''}.")
            self._go("success")
        elif kind == "done" and self.step != "success":
            self.busy = False
            if detail == "0" and not self.err.isVisible():
                self._show_error("Login did not complete. Check the SteamCMD log.")
            self._refresh()

    def _show_error(self, text):
        self.err.setText(text)
        self.err.show()
        self._go("creds")
