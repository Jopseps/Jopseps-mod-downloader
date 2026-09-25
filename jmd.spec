# PyInstaller spec for J Mod Downloader. Build: pyinstaller jmd.spec  → dist/JModDownloader/
# One-folder build on purpose: QtWebEngine ships a helper process + resources that one-file mode unpacks slowly.
import sys

block_cipher = None

a = Analysis(
    ["jmd/__main__.py"],
    pathex=["."],
    datas=[("jmd/assets", "jmd/assets")],
    hiddenimports=[
        # handlers are discovered with pkgutil at runtime, so name them for the analyzer
        "jmd.handlers.generic",
        "jmd.handlers.rimworld",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebChannel",
        "PySide6.QtSvg",
        "PySide6.QtNetwork",
    ],
    excludes=["tkinter", "PySide6.Qt3DCore", "PySide6.QtQuick3D", "PySide6.QtCharts", "PySide6.QtDataVisualization",
              "PySide6.QtMultimedia", "PySide6.QtBluetooth", "PySide6.QtSensors", "PySide6.QtSerialPort"],
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="JModDownloader",
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, upx=False, name="JModDownloader")
