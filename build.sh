#!/usr/bin/env bash
# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
# Local Linux build: dist/JModManager/ + dist/JModManager-Linux.tar.gz
# Needs only Python 3. Dependencies go into .venv (pip comes from Python's own ensurepip), not the system.
# A local build bundles this PC's libraries, so it runs here and on newer distros; releases are built by CI.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if [ ! -x .venv/bin/python ]; then
    echo "==> Creating .venv"
    "$PY" -m venv .venv
fi

echo "==> Installing dependencies"
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt pyinstaller

echo "==> Tests"
.venv/bin/python -m unittest tests.test_core tests.test_manager tests.test_tts

echo "==> Building"
.venv/bin/python -m PyInstaller --noconfirm jmd.spec
tar -C dist -czf dist/JModManager-Linux.tar.gz JModManager

echo "==> Done: dist/JModManager/JModManager (archive: dist/JModManager-Linux.tar.gz)"
