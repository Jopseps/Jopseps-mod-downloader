# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
# Icon paths derived from Lucide (ISC) and Feather (MIT), see jmd/assets/LICENSE-Lucide.txt
"""Lucide-style line icons (paths copied from the design), tinted at runtime."""
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

PATHS = {
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "chevron-right": '<path d="m9 18 6-6-6-6"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    "download": '<path d="M12 3v12m-5-5 5 5 5-5M4 21h16"/>',
    "refresh": '<path d="M21 12a9 9 0 1 1-2.64-6.36L21 8"/><path d="M21 3v5h-5"/>',
    "back": '<path d="m12 19-7-7 7-7M19 12H5"/>',
    "forward": '<path d="M5 12h14m-7-7 7 7-7 7"/>',
    "home": '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/>',
    "lock": '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "terminal": '<path d="m4 17 6-6-6-6M12 19h8"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "warn": '<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17h.01"/>',
    "settings": ('<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73'
                 'l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38'
                 'a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18'
                 'a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08'
                 'a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08'
                 'a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>'),
}

_cache = {}


def renderer(name, color, stroke=2.0):
    key = (name, color, stroke)
    if key not in _cache:
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
               f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{PATHS[name]}</svg>')
        _cache[key] = QSvgRenderer(QByteArray(svg.encode()))
    return _cache[key]


def paint(painter, name, rect, color, stroke=2.0):
    renderer(name, color, stroke).render(painter, QRectF(rect))


def pixmap(name, color, size=16, stroke=2.0, dpr=2.0):
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.fill(Qt.transparent)
    pm.setDevicePixelRatio(dpr)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    paint(p, name, QRectF(0, 0, size, size), color, stroke)
    p.end()
    return pm


def icon(name, color, size=16, stroke=2.0, hover=None, disabled=None):
    ic = QIcon()
    ic.addPixmap(pixmap(name, color, size, stroke), QIcon.Normal)
    if hover:
        ic.addPixmap(pixmap(name, hover, size, stroke), QIcon.Active)
    if disabled:
        ic.addPixmap(pixmap(name, disabled, size, stroke), QIcon.Disabled)
    return ic
