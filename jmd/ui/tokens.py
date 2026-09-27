# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Design tokens from the Claude Design system (Design System.dc.html). Single source for QSS and painting."""

C = {
    # surface
    "bg": "#171a21", "panel": "#1b2838", "panel-alt": "#1f2d3c", "sunken": "#121820", "raised": "#2a475e",
    "row-hover": "#202e3d", "row-selected": "#263b50", "menu": "#1f2b38", "group-hover": "#243546",
    "deep": "#0f1318", "black": "#000000", "skeleton": "#2a3542", "thumb-empty": "#26313d",
    # line
    "border": "#2a3a4b", "border-strong": "#3b5166", "border-hover": "#4d6780", "divider": "#223040",
    # text
    "text": "#c7d5e0", "text-strong": "#e6eef4", "text-dim": "#8f98a0", "text-faint": "#5f6f7e",
    "text-disabled": "#4a5866", "steam-blue": "#66c0f4", "link-hover": "#9fd8fa",
    # accent
    "accent": "#f0609e", "accent-hover": "#f57db1", "accent-pressed": "#d64c88", "on-accent": "#1a0d14",
    "accent-soft": "#2b1c26", "accent-soft-line": "#6d3558", "accent-soft-text": "#f59cc3",
    # control
    "btn-secondary": "#232f3c", "btn-secondary-hover": "#2b3a4a", "btn-secondary-pressed": "#1d2733",
    "btn-disabled": "#26313d", "ghost-hover": "#22313f", "ghost-pressed": "#18222e",
    "danger": "#e5534b", "danger-hover": "#3a1f22", "danger-line": "#6b2c2c", "danger-pressed": "#2c181a",
    "danger-text": "#f2a39d", "toast": "#26394c", "toast-line": "#3b5f7c",
}

# status: (label, fg, bg, line)
STATUS = {
    "queued": ("Queued", "#8f98a0", "#232f3c", "#3b5166"),
    "resolving": ("Resolving…", "#6b7f92", "#1f2833", "#2f4254"),
    "downloading": ("Downloading", "#66c0f4", "#17324a", "#2a5a80"),
    "retrying": ("Retrying", "#ef8a3c", "#3a2716", "#7a4a22"),
    "done": ("Done", "#6fbf4a", "#1e3320", "#3d6b2f"),
    "failed": ("Failed", "#e5534b", "#3a1f22", "#6b2c2c"),
    "outdated": ("Outdated", "#e8cb4e", "#3a3320", "#6b5a24"),
    "login": ("Needs login", "#a78bfa", "#2a2340", "#5b4a94"),
    "skipped": ("Skipped", "#5f6f7e", "#1f2833", "#2a3a4b"),
}
LOGIN_TEXT = "#c9b8ff"

FONT_UI = "Inter"
FONT_MONO = "JetBrains Mono"

# (size px, weight)
TYPE = {
    "display": (20, 700), "title": (16, 600), "heading": (14, 600), "body": (13, 400), "body-strong": (13, 600),
    "small": (12, 400), "caption": (11, 600), "mono": (12, 400), "mono-log": (11.5, 400),
}

SIZE = {
    "row": 56, "group": 36, "thumb": 40, "btn-lg": 34, "btn": 30, "btn-sm": 24, "input": 30, "topbar": 40,
    "tabs": 36, "navbar": 36, "log": 28, "log-open": 180, "left": 360, "left-min": 280,
}


def status_color(status):
    return STATUS.get(status, STATUS["queued"])[1]


def qss():
    """Application stylesheet. QSS has no variables, so tokens are formatted in here."""
    c = C
    return f"""
* {{ font-family: "{FONT_UI}"; font-size: 13px; }}
QWidget {{ color: {c['text']}; }}
QMainWindow, QDialog, #Window {{ background: {c['bg']}; }}
QToolTip {{ background: {c['menu']}; color: {c['text-strong']}; border: 1px solid {c['border-strong']}; padding: 4px 6px; }}

/* === BUTTONS === */
QPushButton {{ min-height: 28px; padding: 0 14px; background: {c['btn-secondary']}; border: 1px solid {c['border-strong']};
  border-radius: 3px; font-weight: 600; color: {c['text']}; }}
QPushButton:hover {{ background: {c['btn-secondary-hover']}; }}
QPushButton:pressed {{ background: {c['btn-secondary-pressed']}; }}
QPushButton:focus {{ border-color: {c['accent']}; outline: none; }}
QPushButton:disabled {{ background: {c['btn-disabled']}; border-color: {c['border']}; color: {c['text-faint']}; }}
QPushButton[size="lg"] {{ min-height: 32px; max-height: 34px; padding: 0 16px; }}
QPushButton[size="sm"] {{ min-height: 22px; max-height: 24px; padding: 0 8px; font-size: 12px; }}

QPushButton[kind="primary"] {{ background: {c['accent']}; border-color: {c['accent']}; color: {c['on-accent']}; font-weight: 700; }}
QPushButton[kind="primary"]:hover {{ background: {c['accent-hover']}; border-color: {c['accent-hover']}; }}
QPushButton[kind="primary"]:pressed {{ background: {c['accent-pressed']}; border-color: {c['accent-pressed']}; }}
QPushButton[kind="primary"]:focus {{ border-color: #ffffff; }}
QPushButton[kind="primary"]:disabled {{ background: {c['btn-disabled']}; border-color: {c['border']}; color: {c['text-faint']}; }}

QPushButton[kind="ghost"] {{ background: transparent; border-color: transparent; color: {c['text-dim']}; font-weight: 500; }}
QPushButton[kind="ghost"]:hover {{ background: {c['ghost-hover']}; color: {c['text-strong']}; }}
QPushButton[kind="ghost"]:pressed {{ background: {c['ghost-pressed']}; }}
QPushButton[kind="ghost"]:focus {{ border-color: {c['accent']}; }}
QPushButton[kind="ghost"]:disabled {{ color: {c['text-disabled']}; }}

QPushButton[kind="icon"] {{ background: transparent; border: 1px solid transparent; padding: 0; min-height: 0;
  color: {c['text']}; }}
QPushButton[kind="icon"]:hover {{ background: {c['ghost-hover']}; }}
QPushButton[kind="icon"]:pressed {{ background: {c['ghost-pressed']}; }}
QPushButton[kind="icon"]:focus {{ border-color: {c['accent']}; }}

QPushButton[kind="danger"] {{ background: transparent; border-color: {c['danger-line']}; color: {c['danger']}; }}
QPushButton[kind="danger"]:hover {{ background: {c['danger-hover']}; }}
QPushButton[kind="danger"]:pressed {{ background: {c['danger-pressed']}; }}
QPushButton[kind="danger"]:focus {{ border-color: {c['danger']}; }}

QPushButton[kind="login"] {{ background: {STATUS['login'][2]}; border-color: {STATUS['login'][3]}; color: {LOGIN_TEXT}; }}
QPushButton[kind="login"]:hover {{ background: #342b52; }}

QPushButton[kind="link"] {{ background: transparent; border: none; padding: 0; min-height: 0; font-weight: 400;
  font-size: 12px; color: {c['steam-blue']}; text-align: left; }}
QPushButton[kind="link"]:hover {{ color: {c['link-hover']}; text-decoration: underline; }}

QPushButton[kind="tab"] {{ background: transparent; border: none; border-bottom: 2px solid transparent; border-radius: 0;
  padding: 0 10px; min-height: 34px; color: {c['text-dim']}; }}
QPushButton[kind="tab"]:hover {{ color: {c['text-strong']}; }}
QPushButton[kind="tab"][active="true"] {{ color: {c['text-strong']}; border-bottom-color: {c['accent']}; }}

QPushButton[kind="select"] {{ background: {c['sunken']}; border-color: {c['border']}; text-align: left; padding: 0 8px;
  font-weight: 600; min-height: 26px; }}
QPushButton[kind="select"]:hover {{ border-color: {c['border-strong']}; background: {c['sunken']}; }}
QPushButton[kind="select"]:pressed {{ background: #0f141b; }}
QPushButton[kind="select"]::menu-indicator {{ width: 0; image: none; }}

QPushButton[kind="profile"] {{ background: {c['panel']}; border-color: {c['border']}; padding: 0 8px 0 6px; font-weight: 600;
  min-height: 26px; }}
QPushButton[kind="profile"]:hover {{ background: {c['ghost-hover']}; border-color: {c['border-strong']}; }}
QPushButton[kind="profile"]::menu-indicator {{ width: 0; image: none; }}

QPushButton[kind="option"] {{ background: {c['sunken']}; border-color: {c['border']}; text-align: left; padding: 10px;
  font-weight: 400; }}
QPushButton[kind="option"]:hover {{ background: #161e28; }}
QPushButton[kind="option"]:checked {{ border-color: {c['accent']}; }}

QPushButton[kind="game"] {{ background: transparent; border-color: transparent; text-align: left; padding: 0 8px;
  font-weight: 400; min-height: 36px; }}
QPushButton[kind="game"]:hover {{ background: {c['ghost-hover']}; }}
QPushButton[kind="game"]:checked {{ background: {c['row-selected']}; border-color: {c['accent']}; }}

/* === INPUTS === */
QLineEdit, QPlainTextEdit, QSpinBox {{ background: {c['sunken']}; border: 1px solid {c['border']}; border-radius: 3px;
  padding: 0 8px; min-height: 28px; color: {c['text']}; selection-background-color: {c['accent-soft-line']}; }}
QLineEdit:hover, QPlainTextEdit:hover, QSpinBox:hover {{ border-color: {c['border-strong']}; }}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus {{ border-color: {c['accent']}; }}
QLineEdit:disabled {{ background: #1a212b; border-color: #222c38; color: {c['text-disabled']}; }}
QLineEdit[error="true"] {{ border-color: {c['danger-line']}; }}
QLineEdit[mono="true"] {{ font-family: "{FONT_MONO}"; font-size: 12px; }}
QLineEdit#GuardCode {{ font-family: "{FONT_MONO}"; font-size: 24px; min-height: 46px; letter-spacing: 12px; color: {c['text-strong']}; }}
QPlainTextEdit#Paste {{ border-style: dashed; border-color: {c['border-strong']}; font-family: "{FONT_MONO}";
  font-size: 12px; padding: 4px 6px; }}
QPlainTextEdit#Paste:hover {{ border-color: {c['border-hover']}; }}
QPlainTextEdit#Paste:focus {{ border-style: solid; border-color: {c['accent']}; }}

/* === MENUS === */
QMenu {{ background: {c['menu']}; border: 1px solid {c['border-strong']}; border-radius: 4px; padding: 4px 0; }}
QMenu::item {{ padding: 7px 24px 7px 12px; color: {c['text']}; }}
QMenu::item:selected {{ background: {c['raised']}; }}
QMenu::item:disabled {{ color: {c['text-faint']}; }}
QMenu::separator {{ height: 1px; background: {c['border']}; margin: 4px 0; }}
QMenu::icon {{ padding-left: 8px; }}

/* === SCROLLBARS === */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #2f4254; border: 2px solid transparent; border-radius: 5px; min-height: 24px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: #2f4254; border-radius: 5px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* === STRUCTURE === */
#TopBar {{ background: {c['bg']}; border-bottom: 1px solid {c['black']}; }}
#Wordmark {{ font-weight: 700; color: {c['text-strong']}; }}
#LeftPanel {{ background: {c['panel']}; }}
#TabBar {{ background: {c['bg']}; border-bottom: 1px solid {c['border']}; }}
#QueueTop {{ background: {c['panel']}; }}
#TreeFrame {{ border-top: 1px solid {c['border']}; background: {c['panel']}; }}
#Footer {{ background: {c['bg']}; border-top: 1px solid {c['border']}; }}
#InstHeader {{ border-bottom: 1px solid {c['border']}; background: {c['panel']}; }}
#RunBox {{ background: {c['sunken']}; border: 1px solid {c['border-strong']}; border-radius: 3px; }}
#NavBar {{ background: {c['bg']}; border-bottom: 1px solid {c['black']}; }}
#UrlBox {{ background: {c['sunken']}; border: 1px solid {c['border']}; border-radius: 3px; }}
#UrlBox[editing="true"] {{ border-color: {c['accent']}; }}
QLineEdit#UrlEdit {{ background: transparent; border: none; padding: 0; font-family: "{FONT_MONO}"; font-size: 11.5px; color: {c['text-strong']}; }}
#ModeSwitch {{ background: {c['sunken']}; border: 1px solid {c['border']}; border-radius: 4px; }}
QPushButton[kind="seg"] {{ background: transparent; border: none; border-radius: 3px; min-height: 22px; max-height: 22px;
  padding: 0 12px; color: {c['text-dim']}; font-size: 12px; }}
QPushButton[kind="seg"]:hover {{ color: {c['text-strong']}; }}
QPushButton[kind="seg"]:checked {{ background: {c['raised']}; color: {c['text-strong']}; }}
#ManageView {{ background: {c['panel']}; }}
#ModColumn {{ background: {c['panel']}; }}
#ColHeader {{ background: {c['bg']}; border-bottom: 1px solid {c['border']}; }}
#ColFilter {{ background: {c['panel']}; border-bottom: 1px solid {c['border']}; }}
#Details, #DetailsBody {{ background: {c['panel-alt']}; }}
#InfoBanner {{ background: {STATUS['outdated'][2]}; border-bottom: 1px solid {STATUS['outdated'][3]};
  color: {STATUS['outdated'][1]}; padding: 8px 14px; font-size: 12px; }}
#LogPanel {{ background: {c['sunken']}; border-top: 1px solid {c['black']}; }}
#LogHeader:hover {{ background: #171f29; }}
QPlainTextEdit#Log {{ background: {c['sunken']}; border: none; border-top: 1px solid #1e2935; border-radius: 0;
  font-family: "{FONT_MONO}"; font-size: 11.5px; color: {c['text-dim']}; padding: 4px 8px; }}
#DialogFooter {{ background: {c['bg']}; border-top: 1px solid {c['border']}; }}
#DialogBody {{ background: {c['panel']}; }}
#StepHeader {{ background: {c['panel']}; border-bottom: 1px solid {c['border']}; }}
#Card {{ background: {c['sunken']}; border: 1px solid {c['border']}; border-radius: 3px; }}
#CardOk {{ background: #15241a; border: 1px solid #2f5a2a; border-radius: 3px; }}
#CardErr {{ background: #2a1a1d; border: 1px solid {c['danger-line']}; border-radius: 3px; }}
#ErrBanner {{ background: {c['danger-hover']}; border: 1px solid {c['danger-line']}; border-radius: 3px; color: {c['danger-text']}; }}
#CodeBox {{ background: #0d1117; border: 1px solid {c['border']}; border-radius: 3px; font-family: "{FONT_MONO}";
  font-size: 12px; color: {c['text-strong']}; padding: 8px 10px; }}
#Toast {{ background: {c['toast']}; border: 1px solid {c['toast-line']}; border-radius: 3px; color: {c['text-strong']};
  font-size: 12px; }}
#PickerLeft {{ border-right: 1px solid {c['border']}; }}
QSplitter::handle {{ background: {c['deep']}; border-left: 1px solid {c['black']}; }}
QSplitter::handle:hover {{ background: {c['raised']}; }}
QProgressBar {{ background: #0d1117; border: none; border-radius: 3px; max-height: 6px; min-height: 6px; }}
QProgressBar::chunk {{ background: {c['steam-blue']}; border-radius: 3px; }}
QTreeView, QListView {{ background: {c['panel']}; border: none; outline: 0; }}
QLabel[role="dim"] {{ color: {c['text-dim']}; font-size: 12px; }}
QLabel[role="faint"] {{ color: {c['text-faint']}; font-size: 11px; }}
QLabel[role="section"] {{ color: {c['text-dim']}; font-size: 12px; font-weight: 600; }}
QLabel[role="caps"] {{ color: {c['text-faint']}; font-size: 11px; font-weight: 600; letter-spacing: 0.5px; }}
QLabel[role="strong"] {{ color: {c['text-strong']}; font-weight: 600; }}
QLabel[role="heading"] {{ color: {c['text-strong']}; font-size: 15px; font-weight: 600; }}
QLabel[role="display"] {{ color: {c['text-strong']}; font-size: 16px; font-weight: 600; }}
QLabel[role="mono"] {{ font-family: "{FONT_MONO}"; font-size: 12px; }}
QLabel[role="monodim"] {{ font-family: "{FONT_MONO}"; font-size: 11px; color: {c['text-dim']}; }}
QLabel[role="badge"] {{ background: {c['border']}; color: {c['text']}; border-radius: 8px; font-size: 11px; font-weight: 600;
  padding: 0 5px; min-width: 10px; min-height: 16px; max-height: 16px; qproperty-alignment: AlignCenter; }}
QLabel[role="badge-warn"] {{ background: {STATUS['outdated'][2]}; border: 1px solid {STATUS['outdated'][3]};
  color: {STATUS['outdated'][1]}; border-radius: 8px; font-size: 10px; font-weight: 700; padding: 0 5px;
  min-height: 14px; max-height: 16px; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {c['border-strong']}; border-radius: 2px;
  background: {c['sunken']}; }}
QCheckBox::indicator:checked {{ background: {c['accent']}; border-color: {c['accent']}; }}
"""
