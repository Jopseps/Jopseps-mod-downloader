import os
import sys

from PySide6.QtCore import QCoreApplication, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

if sys.platform.startswith("linux"):
    # when Qt decides GBM is unsupported, Chromium hands frames over through Vulkan, which segfaults inside Mesa
    # on some drivers; software compositing skips both paths and still rasterizes on the GPU
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    if "--disable-gpu" not in flags:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (flags + " --disable-gpu-compositing").strip()

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
    smoke = os.environ.get("JMD_SMOKE")
    if smoke:
        # CI / packaging self-check: start, report what loaded, quit
        from jmd import handlers
        from jmd.ui.browser_pane import HAVE_WEB

        def report():
            fonts = sorted(set(QFontDatabase.families()) & {"Inter", "JetBrains Mono"})
            line = f"SMOKE ok handlers={sorted(handlers._load())} web={HAVE_WEB} fonts={fonts}"
            print(line, flush=True)
            # windowed Windows builds have no stdout, so leave a file too
            with open(os.path.join(paths.ensure(paths.data_dir()), "smoke.txt"), "w", encoding="utf-8") as f:
                f.write(line + "\n")
            app.quit()
        QTimer.singleShot(int(smoke) if smoke.isdigit() else 3000, report)
    elif not ctl.settings.onboarded or not ctl.profiles:
        QTimer.singleShot(150, win.open_onboarding)
    return app.exec()
