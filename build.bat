@echo off
rem Copyright (C) 2025-2026 Yusuf Mert Turan
rem SPDX-License-Identifier: AGPL-3.0-or-later
rem Local Windows build: dist\JModManager\ + dist\JModManager-Windows.zip
rem Needs only Python 3 from python.org. Dependencies go into .venv, not the system.
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
    echo ==^> Creating .venv
    py -3 -m venv .venv 2>nul || python -m venv .venv
)
if not exist .venv\Scripts\python.exe (
    echo Python 3 not found. Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
    pause
    exit /b 1
)

echo ==^> Installing dependencies
.venv\Scripts\python -m pip install --quiet --upgrade pip || (echo Build failed. & pause & exit /b 1)
.venv\Scripts\python -m pip install --quiet -r requirements.txt pyinstaller || (echo Build failed. & pause & exit /b 1)

echo ==^> Tests
.venv\Scripts\python -m unittest tests.test_core tests.test_manager || (echo Build failed. & pause & exit /b 1)

echo ==^> Building
.venv\Scripts\python -m PyInstaller --noconfirm jmd.spec || (echo Build failed. & pause & exit /b 1)
powershell -NoProfile -Command "Compress-Archive -Force -Path dist\JModManager -DestinationPath dist\JModManager-Windows.zip" || (echo Build failed. & pause & exit /b 1)

echo ==^> Done: dist\JModManager\JModManager.exe (archive: dist\JModManager-Windows.zip)
pause
