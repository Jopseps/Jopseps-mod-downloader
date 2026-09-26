# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
"""First run: 1 SteamCMD (find / auto-install / missing-libs error) → 2 first profile → 3 ready."""
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QStackedWidget,
                               QVBoxLayout, QWidget)

from jmd.core import steamcmd
from jmd.ui import icons
from jmd.ui.async_task import EventPipe, run_async
from jmd.ui.dialogs.common import GamePicker
from jmd.ui.tokens import C, STATUS
from jmd.ui.widgets import Dialog, Spinner, button, label


def _home(path):
    return path.replace(os.path.expanduser("~"), "~")


class StepDot(QWidget):
    def __init__(self, n, text, line, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.n = n
        self.dot = QLabel(str(n))
        self.dot.setFixedSize(20, 20)
        self.dot.setAlignment(Qt.AlignCenter)
        self.text = QLabel(text)
        lay.addWidget(self.dot)
        lay.addWidget(self.text)
        if line:
            ln = QFrame()
            ln.setFixedSize(40, 1)
            ln.setStyleSheet(f"background:{C['border']};")
            lay.addWidget(ln)

    def set_state(self, current):
        on, done = self.n == current, self.n < current
        bg = C["accent"] if on else C["raised"] if done else C["sunken"]
        bd = C["accent"] if on else C["raised"] if done else C["border-strong"]
        fg = C["on-accent"] if on else C["text-strong"] if done else C["text-dim"]
        self.dot.setText("✓" if done else str(self.n))
        self.dot.setStyleSheet(f"background:{bg};border:1px solid {bd};border-radius:10px;color:{fg};"
                               f"font-size:11px;font-weight:700;")
        tc = C["text-strong"] if on else C["text"] if done else C["text-faint"]
        self.text.setStyleSheet(f"color:{tc};font-weight:600;")


class OnboardingDialog(Dialog):
    def __init__(self, controller, thumbs, parent=None):
        super().__init__("Set up J Mod Downloader", 760, parent)
        self.ctl = controller
        self.step = 1
        self.exe = steamcmd.locate(controller.settings.steamcmd_path)

        # === STEP HEADER ===
        head = QFrame()
        head.setObjectName("StepHeader")
        hl = QVBoxLayout(head)
        hl.setContentsMargins(16, 16, 16, 14)
        hl.setSpacing(12)
        hl.addWidget(label("Set up J Mod Downloader", "display"))
        dots = QHBoxLayout()
        dots.setSpacing(10)
        self.dots = [StepDot(1, "SteamCMD", True), StepDot(2, "First profile", True), StepDot(3, "Done", False)]
        for d in self.dots:
            dots.addWidget(d)
        dots.addStretch(1)
        hl.addLayout(dots)
        self.header.addWidget(head)

        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.pages = QStackedWidget()
        self.body_layout.addWidget(self.pages)
        self.pages.addWidget(self._build_steamcmd())
        self.picker = GamePicker(thumbs)
        self.picker.changed.connect(self._refresh)
        self.pages.addWidget(self.picker)
        self.pages.addWidget(self._build_ready())

        self.back = button("Back", "ghost")
        self.back.clicked.connect(lambda: self._go(self.step - 1))
        self.next = button("Next", "primary")
        self.next.clicked.connect(self._next)
        self.footer_layout.addWidget(self.back)
        self.footer_layout.addStretch(1)
        self.footer_layout.addWidget(self.next)
        self._pipe = EventPipe(self._install_progress, self)
        self._show_cmd_state("found" if self.exe else "missing")
        self._go(1)

    # === STEP 1 ===
    def _build_steamcmd(self):
        w = QWidget()
        w.setMinimumHeight(300)
        l = QVBoxLayout(w)
        l.setContentsMargins(20, 24, 20, 24)
        l.setSpacing(14)
        l.addWidget(label("SteamCMD", "heading"))
        intro = label("J Mod Downloader fetches Workshop items with SteamCMD, Valve's command-line client.", "dim", wrap=True)
        intro.setStyleSheet(f"color:{C['text-dim']};font-size:13px;")
        l.addWidget(intro)
        self.cmd_states = QStackedWidget()

        # missing
        m = QWidget()
        ml = QVBoxLayout(m)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(14)
        card = QFrame()
        card.setObjectName("Card")
        cl = QHBoxLayout(card)
        cl.setContentsMargins(12, 12, 12, 12)
        cl.setSpacing(10)
        ic = QLabel()
        ic.setPixmap(icons.pixmap("warn", STATUS["outdated"][1], 16))
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(label("Not found", "strong"))
        col.addWidget(label(f"Checked {steamcmd.searched_places()}.", "dim", wrap=True))
        cl.addWidget(ic)
        cl.addLayout(col, 1)
        ml.addWidget(card)
        row = QHBoxLayout()
        row.setSpacing(8)
        dl = button("Download SteamCMD automatically", "primary", "lg", icon="download")
        dl.clicked.connect(self._install)
        br = button("Browse…", size="lg")
        br.clicked.connect(self._browse)
        row.addWidget(dl)
        row.addWidget(br)
        row.addStretch(1)
        ml.addLayout(row)
        ml.addStretch(1)
        self.cmd_states.addWidget(m)

        # installing
        i = QFrame()
        i.setObjectName("Card")
        il = QVBoxLayout(i)
        il.setContentsMargins(14, 14, 14, 14)
        il.setSpacing(8)
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(Spinner())
        top.addWidget(label("Installing SteamCMD…", "strong"))
        top.addStretch(1)
        self.inst_pct = QLabel("0%")
        self.inst_pct.setStyleSheet(f"font-family:'JetBrains Mono';font-size:12px;color:{C['steam-blue']};")
        top.addWidget(self.inst_pct)
        il.addLayout(top)
        self.inst_bar = QProgressBar()
        self.inst_bar.setTextVisible(False)
        il.addWidget(self.inst_bar)
        self.inst_line = label("", "monodim")
        il.addWidget(self.inst_line)
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.addWidget(i)
        wl.addStretch(1)
        self.cmd_states.addWidget(wrap)

        # error
        e = QWidget()
        el = QVBoxLayout(e)
        el.setContentsMargins(0, 0, 0, 0)
        el.setSpacing(14)
        ecard = QFrame()
        ecard.setObjectName("CardErr")
        ecl = QVBoxLayout(ecard)
        ecl.setContentsMargins(14, 14, 14, 14)
        ecl.setSpacing(10)
        self.err_title = QLabel()
        self.err_title.setWordWrap(True)
        self.err_title.setStyleSheet(f"color:{C['danger-text']};font-weight:600;")
        self.err_detail = QLabel()
        self.err_detail.setWordWrap(True)
        self.err_detail.setStyleSheet("font-family:'JetBrains Mono';font-size:11px;color:#c79a96;")
        self.err_hint_lbl = label("Install them, then retry:")
        self.err_hint = QLabel()
        self.err_hint.setObjectName("CodeBox")
        self.err_hint.setTextInteractionFlags(Qt.TextSelectableByMouse)
        for wdg in (self.err_title, self.err_detail, self.err_hint_lbl, self.err_hint):
            ecl.addWidget(wdg)
        el.addWidget(ecard)
        row = QHBoxLayout()
        retry = button("Retry", "primary", "lg")
        retry.clicked.connect(self._retry)
        br2 = button("Browse…", size="lg")
        br2.clicked.connect(self._browse)
        row.addWidget(retry)
        row.addWidget(br2)
        row.addStretch(1)
        el.addLayout(row)
        el.addStretch(1)
        self.cmd_states.addWidget(e)

        # found
        f = QWidget()
        fl = QVBoxLayout(f)
        fl.setContentsMargins(0, 0, 0, 0)
        fcard = QFrame()
        fcard.setObjectName("CardOk")
        fcl = QHBoxLayout(fcard)
        fcl.setContentsMargins(12, 12, 12, 12)
        fcl.setSpacing(10)
        fic = QLabel()
        fic.setPixmap(icons.pixmap("check", STATUS["done"][1], 16, 2.5))
        col = QVBoxLayout()
        col.setSpacing(0)
        self.found_lbl = QLabel()
        self.found_lbl.setStyleSheet(f"color:{C['text-strong']};font-weight:600;")
        col.addWidget(self.found_lbl)
        col.addWidget(label("Runs anonymously", "dim"))
        change = button("Change…", "ghost")
        change.clicked.connect(self._browse)
        fcl.addWidget(fic)
        fcl.addLayout(col, 1)
        fcl.addWidget(change)
        fl.addWidget(fcard)
        fl.addStretch(1)
        self.cmd_states.addWidget(f)
        l.addWidget(self.cmd_states, 1)
        return w

    def _show_cmd_state(self, state, err=None):
        self.cmd_state = state
        self.cmd_states.setCurrentIndex(["missing", "installing", "error", "found"].index(state))
        if state == "found":
            self.found_lbl.setText(f'Found at <span style="font-family:\'JetBrains Mono\';font-size:12px">'
                                   f'{_home(self.exe)}</span>')
        if state == "error":
            if isinstance(err, steamcmd.MissingLibsError):
                self.err_title.setText("SteamCMD installed but can't start: 32-bit libraries are missing.")
                self.err_detail.setText(f"error while loading shared libraries: {err.lib}")
                self.err_hint.setText(err.hint)
                self.err_hint_lbl.show()
                self.err_hint.show()
            else:
                self.err_title.setText("SteamCMD could not be installed.")
                self.err_detail.setText(str(err))
                self.err_hint_lbl.hide()
                self.err_hint.hide()
        self._refresh()

    def _install(self):
        self._show_cmd_state("installing")
        self._install_progress(0, "Starting…")
        run_async(lambda: steamcmd.bootstrap(progress=self._pipe), self._installed,
                  lambda e: self._show_cmd_state("error", e))

    def _install_progress(self, pct, line):
        self.inst_bar.setValue(int(pct))
        self.inst_pct.setText(f"{int(pct)}%")
        self.inst_line.setText(self.inst_line.fontMetrics().elidedText(_home(line), Qt.ElideRight, 600))

    def _installed(self, exe):
        self.exe = exe
        self.ctl.settings.steamcmd_path = exe
        self.ctl.save_settings()
        self._show_cmd_state("found")

    def _retry(self):
        if self.exe:
            run_async(lambda: steamcmd.first_run(self.exe), lambda _: self._show_cmd_state("found"),
                      lambda e: self._show_cmd_state("error", e))
        else:
            self._install()

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "SteamCMD folder", os.path.expanduser("~"))
        exe = steamcmd.resolve_exe(path) if path else None
        if exe:
            self.exe = exe
            self.ctl.settings.steamcmd_path = exe
            self.ctl.save_settings()
            self._show_cmd_state("found")
        elif path:
            self.ctl.toast.emit("No SteamCMD launcher in that folder")

    # === STEP 3 ===
    def _build_ready(self):
        w = QWidget()
        w.setMinimumHeight(300)
        l = QVBoxLayout(w)
        l.setContentsMargins(20, 24, 20, 24)
        l.setSpacing(14)
        l.addWidget(label("Ready", "heading"))
        self.ready_intro = label("", "dim")
        self.ready_intro.setStyleSheet(f"color:{C['text-dim']};font-size:13px;")
        l.addWidget(self.ready_intro)
        card = QFrame()
        card.setObjectName("Card")
        self.grid = QGridLayout(card)
        self.grid.setContentsMargins(14, 14, 14, 14)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(8)
        self.grid.setColumnMinimumWidth(0, 120)
        self.grid.setColumnStretch(1, 1)
        self.ready_vals = {}
        for r, key in enumerate(("SteamCMD", "Profile", "Mod folder", "Sync mode", "Handler")):
            k = label(key)
            k.setStyleSheet(f"color:{C['text-dim']};")
            v = QLabel()
            v.setWordWrap(True)
            if key in ("SteamCMD", "Mod folder"):
                v.setStyleSheet("font-family:'JetBrains Mono';font-size:12px;")
            self.grid.addWidget(k, r, 0, Qt.AlignTop)
            self.grid.addWidget(v, r, 1)
            self.ready_vals[key] = v
        l.addWidget(card)
        l.addStretch(1)
        return w

    def _fill_ready(self):
        r = self.picker.result()
        self.ready_intro.setText(f"The Workshop for {r['name']} opens next. Click + Add on any mod to queue it.")
        v = self.ready_vals
        v["SteamCMD"].setText(_home(self.exe or ""))
        v["Profile"].setText(f'{r["name"]} <span style="font-family:\'JetBrains Mono\';font-size:11px;'
                             f'color:{C["text-dim"]}">{r["app_id"]}</span>')
        v["Mod folder"].setText(r["mod_dir"] or "SteamCMD folder (no copy)")
        v["Sync mode"].setText("Link" if r["sync_mode"] == "link" else "Copy")
        v["Handler"].setText(self.picker.handler.label)

    # === NAV ===
    def _go(self, step):
        self.step = max(1, min(3, step))
        self.pages.setCurrentIndex(self.step - 1)
        for d in self.dots:
            d.set_state(self.step)
        if self.step == 3:
            self._fill_ready()
        self._refresh()

    def _refresh(self):
        self.back.setVisible(self.step > 1)
        self.next.setText("Open Workshop" if self.step == 3 else "Next")
        if self.step == 1:
            self.next.setEnabled(self.cmd_state == "found")
        elif self.step == 2:
            self.next.setEnabled(self.picker.selected is not None)
        else:
            self.next.setEnabled(True)

    def _next(self):
        if self.step < 3:
            self._go(self.step + 1)
            return
        r = self.picker.result()
        self.ctl.create_profile(r["name"], r["app_id"], r["mod_dir"], r["sync_mode"], r["capsule_url"])
        self.ctl.settings.onboarded = True
        self.ctl.save_settings()
        self.accept()
