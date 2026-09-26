# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
from jmd.ui.dialogs.common import GamePicker
from jmd.ui.widgets import Dialog, button


class ProfileDialog(Dialog):
    def __init__(self, controller, thumbs, parent=None):
        super().__init__("New profile", 760, parent)
        self.ctl = controller
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.picker = GamePicker(thumbs)
        self.body_layout.addWidget(self.picker)
        self.footer_layout.addStretch(1)
        cancel = button("Cancel")
        cancel.clicked.connect(self.reject)
        self.create = button("Create profile", "primary")
        self.create.setEnabled(False)
        self.create.clicked.connect(self._create)
        self.footer_layout.addWidget(cancel)
        self.footer_layout.addWidget(self.create)
        self.picker.changed.connect(lambda: self.create.setEnabled(True))

    def _create(self):
        r = self.picker.result()
        profile = self.ctl.create_profile(r["name"], r["app_id"], r["mod_dir"], r["sync_mode"], r["capsule_url"])
        self.ctl.toast.emit(f'Profile "{profile.name}" created')
        self.accept()
