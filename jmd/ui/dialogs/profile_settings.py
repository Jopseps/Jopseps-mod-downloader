# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Per-profile settings: folders, the game's mod config override, how Play launches the game."""
import os

from PySide6.QtWidgets import QButtonGroup, QFileDialog, QHBoxLayout, QLineEdit, QVBoxLayout

from jmd.core import library, rimworld
from jmd.ui.dialogs.common import OptionCard
from jmd.ui.widgets import Dialog, button, label


def _home(path):
    return path.replace(os.path.expanduser("~"), "~")


class ProfileSettingsDialog(Dialog):
    def __init__(self, controller, mgr, parent=None):
        p = controller.profile
        super().__init__(f"{p.name}: profile settings", 580, parent)
        self.ctl = controller
        self.mgr = mgr
        self.profile = p
        handler = controller.handler
        ctx = mgr.context()
        b = self.body_layout
        b.setSpacing(16)

        self.mod_dir = self._path_row(b, "Mod folder", p.mod_dir, "Where the game loads mods from", folder=True)
        detected = library.install_dir(p.app_id)
        self.game_dir = self._path_row(b, "Game folder", p.game_dir,
                                       _home(detected) if detected else "Not found in your Steam libraries",
                                       folder=True, hint="Leave empty to use the one Steam knows about.")
        self.config = None
        if handler.key == "rimworld":
            found = rimworld.find_config(ctx.libraries)
            self.config = self._path_row(b, "ModsConfig.xml", p.config_path,
                                         _home(found) if found else "Not found: start RimWorld once, or pick it",
                                         filters="ModsConfig (ModsConfig.xml);;XML (*.xml)",
                                         hint="Leave empty to detect it (native or Proton).")

        # === LAUNCH ===
        col = QVBoxLayout()
        col.setSpacing(6)
        col.addWidget(label("Play button", "section"))
        self.steam_card = OptionCard("Through Steam", f"steam://rungameid/{p.app_id}. Keeps the overlay and playtime.")
        self.exe_card = OptionCard("Custom executable", "Starts the file below with its arguments.")
        group = QButtonGroup(self)
        group.addButton(self.steam_card)
        group.addButton(self.exe_card)
        (self.exe_card if p.launch_mode == "exe" else self.steam_card).setChecked(True)
        col.addWidget(self.steam_card)
        col.addWidget(self.exe_card)
        b.addLayout(col)
        self.exe = self._path_row(b, "Executable", p.exe_path, "", filters="All files (*)")
        self.args = QLineEdit(p.exe_args)
        self.args.setProperty("mono", "true")
        self.args.setPlaceholderText("-savedatafolder=…  (optional)")
        b.addWidget(label("Arguments", "section"))
        b.addWidget(self.args)
        self.exe_card.toggled.connect(self._launch_mode)
        self._launch_mode(self.exe_card.isChecked())

        mode = label(f"Sync mode: {p.sync_mode.capitalize()}. Set when the profile was created.", "faint", wrap=True)
        b.addWidget(mode)

        self.footer_layout.addStretch(1)
        cancel = button("Cancel")
        cancel.clicked.connect(self.reject)
        save = button("Save", "primary")
        save.clicked.connect(self._save)
        self.footer_layout.addWidget(cancel)
        self.footer_layout.addWidget(save)

    def _path_row(self, layout, title, value, placeholder, folder=False, filters="", hint=""):
        col = QVBoxLayout()
        col.setSpacing(6)
        col.addWidget(label(title, "section"))
        row = QHBoxLayout()
        row.setSpacing(6)
        edit = QLineEdit(value)
        edit.setProperty("mono", "true")
        edit.setPlaceholderText(placeholder)
        browse = button("Browse…")
        browse.clicked.connect(lambda: self._browse(edit, title, folder, filters))
        row.addWidget(edit, 1)
        row.addWidget(browse)
        col.addLayout(row)
        if hint:
            col.addWidget(label(hint, "faint"))
        layout.addLayout(col)
        edit.browse = browse
        return edit

    def _browse(self, edit, title, folder, filters):
        start = edit.text() or edit.placeholderText().replace("~", os.path.expanduser("~"))
        start = start if os.path.exists(start) else os.path.expanduser("~")
        if folder:
            path = QFileDialog.getExistingDirectory(self, title, start)
        else:
            path, _ = QFileDialog.getOpenFileName(self, title, start, filters)
        if path:
            edit.setText(path)

    def _launch_mode(self, exe):
        for w in (self.exe, self.exe.browse, self.args):
            w.setEnabled(exe)

    def _save(self):
        p = self.profile
        p.mod_dir = self.mod_dir.text().strip()
        p.game_dir = self.game_dir.text().strip()
        if self.config is not None:
            p.config_path = self.config.text().strip()
        p.launch_mode = "exe" if self.exe_card.isChecked() else "steam"
        p.exe_path = self.exe.text().strip()
        p.exe_args = self.args.text().strip()
        self.ctl.save_profile(p)
        self.mgr.refresh()
        self.accept()
