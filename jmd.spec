# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
# PyInstaller spec for J Mod Manager. Build: pyinstaller jmd.spec  → dist/JModManager/
# One-folder build on purpose: QtWebEngine ships a helper process + resources that one-file mode unpacks slowly.
import os
import shutil
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
        "jmd.handlers.tts",
        "jmd.selftest",
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
if sys.platform.startswith("linux"):
    # the user's GPU driver (Mesa) always loads from the system and needs the system's copies of these;
    # bundling the CI runner's older ones breaks EGL and the window never shows on newer distros
    SYSTEM_LIBS = ("libstdc++.so", "libgcc_s.so", "libgbm.so", "libdrm", "libEGL", "libGL", "libexpat.so", "libz.so",
                   "libzstd.so", "libfontconfig.so", "libfreetype.so", "libX11.so", "libX11-xcb.so", "libXau.so",
                   "libXdmcp.so", "libxcb-glx.so", "libxcb-randr.so", "libxcb-shm.so", "libxcb-sync.so",
                   "libxcb-xfixes.so", "libxcb-dri", "libxcb-present.so")
    a.binaries = [b for b in a.binaries if not os.path.basename(b[0]).startswith(SYSTEM_LIBS)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="JModManager",
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, upx=False, name="JModManager")
# AGPL: every copy of the program ships with the license, next to the executable
shutil.copy("LICENSE", os.path.join(DISTPATH, "JModManager", "LICENSE"))
