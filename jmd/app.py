import os
import sys

from PySide6.QtCore import QCoreApplication, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

# QtWebEngine must be imported (and GL contexts shared) before the QApplication exists
if not os.environ.get("JMD_NO_WEB"):
    try:
        import PySide6.QtWebEngineWidgets  # noqa: F401
    except ImportError:
        pass

from jmd import APP_NAME, paths
from jmd.ui.tokens import C, FONT_UI, qss


def load_fonts():
    folder = paths.asset("fonts")
    if not os.path.isdir(folder):
        return
    for name in sorted(os.listdir(folder)):
        if name.endswith(".ttf"):
            QFontDatabase.addApplicationFont(os.path.join(folder, name))


def dark_palette():
    pal = QPalette()
    for role, color in ((QPalette.Window, C["bg"]), (QPalette.Base, C["sunken"]), (QPalette.AlternateBase, C["panel"]),
                        (QPalette.Text, C["text"]), (QPalette.WindowText, C["text"]), (QPalette.Button, C["btn-secondary"]),
                        (QPalette.ButtonText, C["text"]), (QPalette.Highlight, C["accent-soft-line"]),
                        (QPalette.HighlightedText, C["text-strong"]), (QPalette.PlaceholderText, C["text-faint"]),
                        (QPalette.ToolTipBase, C["menu"]), (QPalette.ToolTipText, C["text-strong"])):
        pal.setColor(role, QColor(color))
    return pal


def build_app(argv=None):
    if not QApplication.instance():
        QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication.instance() or QApplication(argv or sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    load_fonts()
    f = QFont(FONT_UI)
    f.setPixelSize(13)
    app.setFont(f)
    app.setPalette(dark_palette())
    app.setStyleSheet(qss())
    return app


def main():
    app = build_app()
    from jmd.ui.controller import AppController
    from jmd.ui.main_window import MainWindow
    ctl = AppController()
    win = MainWindow(ctl)
    win.show()
    if not ctl.settings.onboarded or not ctl.profiles:
        QTimer.singleShot(150, win.open_onboarding)
    return app.exec()
