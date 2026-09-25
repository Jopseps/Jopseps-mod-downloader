import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from jmd import paths
from jmd.core import steamcmd
from jmd.ui import icons
from jmd.ui.async_task import run_async
from jmd.ui.dialogs.common import OptionCard
from jmd.ui.tokens import C, STATUS
from jmd.ui.widgets import Dialog, Line, button, label


def _home(path):
    return path.replace(os.path.expanduser("~"), "~")


class Stepper(QWidget):
    """[−] 3 [+] attempts per item."""

    def __init__(self, value, lo=1, hi=10, parent=None):
        super().__init__(parent)
        self.value, self.lo, self.hi = value, lo, hi
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        style = (f"QPushButton{{min-height:26px;max-height:28px;min-width:30px;max-width:30px;padding:0;border-radius:0;"
                 f"font-size:15px;font-weight:400;border-color:{C['border']};}}")
        self.dec = QPushButton("−")
        self.inc = QPushButton("+")
        self.num = QLabel(str(value))
        self.num.setAlignment(Qt.AlignCenter)
        self.num.setFixedSize(40, 28)
        self.num.setStyleSheet(f"background:{C['sunken']};border-top:1px solid {C['border']};"
                               f"border-bottom:1px solid {C['border']};font-family:'JetBrains Mono';color:{C['text-strong']};")
        for b in (self.dec, self.inc):
            b.setStyleSheet(style)
            b.setCursor(Qt.PointingHandCursor)
        self.dec.clicked.connect(lambda: self.set(self.value - 1))
        self.inc.clicked.connect(lambda: self.set(self.value + 1))
        lay.addWidget(self.dec)
        lay.addWidget(self.num)
        lay.addWidget(self.inc)

    def set(self, v):
        self.value = max(self.lo, min(self.hi, v))
        self.num.setText(str(self.value))


class SettingsDialog(Dialog):
    def __init__(self, controller, thumbs, parent=None):
        super().__init__("Settings", 580, parent)
        self.ctl = controller
        self.thumbs = thumbs
        s = controller.settings
        b = self.body_layout
        b.setSpacing(18)

        # === STEAMCMD ===
        col = QVBoxLayout()
        col.setSpacing(6)
        col.addWidget(label("SteamCMD", "section"))
        row = QHBoxLayout()
        row.setSpacing(6)
        self.cmd = QLineEdit(s.steamcmd_path or (steamcmd.locate() or ""))
        self.cmd.setProperty("mono", "true")
        self.cmd.textChanged.connect(self._check_cmd)
        auto = button("Auto-detect")
        auto.clicked.connect(self._auto)
        self.reinstall = button("Re-install")
        self.reinstall.clicked.connect(self._reinstall)
        row.addWidget(self.cmd, 1)
        row.addWidget(auto)
        row.addWidget(self.reinstall)
        col.addLayout(row)
        status = QHBoxLayout()
        status.setSpacing(6)
        self.cmd_icon = QLabel()
        self.cmd_status = QLabel()
        status.addWidget(self.cmd_icon)
        status.addWidget(self.cmd_status, 1)
        col.addLayout(status)
        b.addLayout(col)

        # === CACHE ===
        col = QVBoxLayout()
        col.setSpacing(6)
        col.addWidget(label("Cache folder", "section"))
        self.cache_app = OptionCard("App-managed (default)", _home(paths.cache_dir()), mono_sub=True)
        self.cache_existing = OptionCard("Use existing SteamCMD folder", "SteamCMD's own steamapps/workshop", mono_sub=True)
        grp = QButtonGroup(self)
        grp.addButton(self.cache_app)
        grp.addButton(self.cache_existing)
        (self.cache_existing if s.cache_mode == "existing" else self.cache_app).setChecked(True)
        col.addWidget(self.cache_app)
        col.addWidget(self.cache_existing)
        b.addLayout(col)

        # === RETRIES + USER ===
        row = QHBoxLayout()
        row.setSpacing(24)
        rc = QVBoxLayout()
        rc.setSpacing(6)
        rc.addWidget(label("Retries", "section"))
        sr = QHBoxLayout()
        sr.setSpacing(8)
        self.retries = Stepper(s.retries)
        sr.addWidget(self.retries)
        sr.addWidget(label("attempts per item", "dim"))
        sr.addStretch(1)
        rc.addLayout(sr)
        uc = QVBoxLayout()
        uc.setSpacing(6)
        uc.addWidget(QLabel(f'<span style="color:{C["text-dim"]};font-size:12px;font-weight:600">Steam username</span> '
                            f'<span style="color:{C["text-faint"]};font-size:12px">(optional)</span>'))
        self.user = QLineEdit(s.username)
        self.user.setPlaceholderText("Anonymous")
        uc.addWidget(self.user)
        uc.addWidget(label("Password is never stored.", "faint"))
        row.addLayout(rc)
        row.addLayout(uc, 1)
        b.addLayout(row)

        # === THUMBNAILS ===
        b.addWidget(Line())
        row = QHBoxLayout()
        row.setSpacing(12)
        tc = QVBoxLayout()
        tc.setSpacing(0)
        tc.addWidget(label("Thumbnail cache", "strong"))
        self.thumb_info = label("", "dim")
        tc.addWidget(self.thumb_info)
        clear = button("Clear thumbnail cache", "danger")
        clear.clicked.connect(self._clear_thumbs)
        row.addLayout(tc, 1)
        row.addWidget(clear)
        b.addLayout(row)
        self._thumb_text()

        self.footer_layout.addStretch(1)
        cancel = button("Cancel")
        cancel.clicked.connect(self.reject)
        save = button("Save", "primary")
        save.clicked.connect(self._save)
        self.footer_layout.addWidget(cancel)
        self.footer_layout.addWidget(save)
        self._check_cmd()

    def _check_cmd(self):
        exe = steamcmd.resolve_exe(self.cmd.text().strip())
        if exe:
            color, icon, text = STATUS["done"][1], "check", "Found"
        else:
            color, icon, text = STATUS["outdated"][1], "warn", "Not found at this path"
        self.cmd_icon.setPixmap(icons.pixmap(icon, color, 13, 2.5))
        self.cmd_status.setText(text)
        self.cmd_status.setStyleSheet(f"color:{color};font-size:12px;")

    def _auto(self):
        exe = steamcmd.locate()
        if exe:
            self.cmd.setText(exe)
            self.ctl.toast.emit(f"Found SteamCMD at {_home(exe)}")
        else:
            self.ctl.toast.emit("SteamCMD not found. Use Re-install.")

    def _reinstall(self):
        self.reinstall.setEnabled(False)
        self.ctl.toast.emit("Re-installing SteamCMD in the background")

        def done(exe):
            self.reinstall.setEnabled(True)
            self.cmd.setText(exe)
            self.ctl.toast.emit("SteamCMD installed")

        def failed(e):
            self.reinstall.setEnabled(True)
            hint = f" Run: {e.hint}" if isinstance(e, steamcmd.MissingLibsError) else ""
            self.ctl.toast.emit(f"Install failed: {e}{hint}")

        run_async(lambda: steamcmd.bootstrap(), done, failed)

    def _thumb_text(self):
        size, count = self.thumbs.disk_usage()
        self.thumb_info.setText(f"{size / 1e6:.0f} MB · {count:,} images" if count else "Empty")

    def _clear_thumbs(self):
        size = self.thumbs.clear()
        self._thumb_text()
        self.ctl.toast.emit(f"Cleared {size / 1e6:.0f} MB" if size else "Cache already empty")

    def _save(self):
        s = self.ctl.settings
        s.steamcmd_path = self.cmd.text().strip()
        s.cache_mode = "existing" if self.cache_existing.isChecked() else "app"
        s.retries = self.retries.value
        s.username = self.user.text().strip()
        self.ctl.save_settings()
        self.ctl.toast.emit("Settings saved")
        self.accept()
