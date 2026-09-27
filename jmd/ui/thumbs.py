# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
import os

from PySide6.QtCore import QObject, QRect, Qt, QUrl, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

from jmd import paths
from jmd.ui.async_task import run_async


def _sized(url, px):
    """Steam's image CDN resizes on request; saves bandwidth for 40px thumbs."""
    if "steamusercontent.com" in url and "?" not in url:
        return f"{url}?imw={px}&imh={px}&ima=fit&impolicy=Letterbox&imcolor=%23000000&letterbox=true"
    return url


class ThumbCache(QObject):
    """Square-cropped thumbnails keyed by Workshop/App id. Memory + disk cache, async fetch."""
    ready = Signal(str)

    def __init__(self, size=80, parent=None):
        super().__init__(parent)
        self.size = size
        self.folder = paths.ensure(paths.thumbs_dir())
        self._mem = {}
        self._pending = set()
        self._net = QNetworkAccessManager(self)

    def get(self, key, url):
        if key in self._mem:
            return self._mem[key]
        path = os.path.join(self.folder, f"{key}.png")
        if os.path.exists(path):
            pm = QPixmap(path)
            if not pm.isNull():
                self._mem[key] = pm
                return pm
        if url and key not in self._pending:
            self._pending.add(key)
            reply = self._net.get(QNetworkRequest(QUrl(_sized(url, self.size))))
            reply.finished.connect(lambda r=reply, k=key: self._done(r, k))
        return None

    def _done(self, reply, key):
        self._pending.discard(key)
        data = reply.readAll()
        reply.deleteLater()
        img = QImage.fromData(bytes(data))
        if img.isNull():
            return
        side = min(img.width(), img.height())
        img = img.copy(QRect((img.width() - side) // 2, (img.height() - side) // 2, side, side))
        img = img.scaled(self.size, self.size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        img.save(os.path.join(self.folder, f"{key}.png"))
        self._mem[key] = QPixmap.fromImage(img)
        self.ready.emit(key)

    def get_file(self, key, path):
        """Thumbnail of a local image (RimWorld About/Preview.png), decoded off the UI thread, memory only."""
        if key in self._mem:
            return self._mem[key]
        if not path or key in self._pending:
            return None
        self._pending.add(key)
        size = self.size

        def load():
            img = QImage(path)
            if img.isNull():
                return None
            side = min(img.width(), img.height())
            img = img.copy(QRect((img.width() - side) // 2, (img.height() - side) // 2, side, side))
            return img.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        def done(img):
            self._pending.discard(key)
            if img is not None:
                self._mem[key] = QPixmap.fromImage(img)
                self.ready.emit(key)

        run_async(load, done, lambda _: self._pending.discard(key))
        return None

    def get_any(self, key, source):
        """URL or local path."""
        if source and not source.startswith(("http://", "https://")):
            return self.get_file(key, source)
        return self.get(key, source)

    def get_wide(self, key, url, w, h):
        """Non-square (game capsules)."""
        key = f"{key}_w"
        if key in self._mem:
            return self._mem[key]
        path = os.path.join(self.folder, f"{key}.png")
        if os.path.exists(path):
            self._mem[key] = QPixmap(path)
            return self._mem[key]
        if url and key not in self._pending:
            self._pending.add(key)
            reply = self._net.get(QNetworkRequest(QUrl(url)))
            reply.finished.connect(lambda r=reply, k=key: self._done_wide(r, k, w, h))
        return None

    def _done_wide(self, reply, key, w, h):
        self._pending.discard(key)
        img = QImage.fromData(bytes(reply.readAll()))
        reply.deleteLater()
        if img.isNull():
            return
        img = img.scaled(w * 2, h * 2, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        img.save(os.path.join(self.folder, f"{key}.png"))
        self._mem[key] = QPixmap.fromImage(img)
        self.ready.emit(key)

    def disk_usage(self):
        total = count = 0
        for name in os.listdir(self.folder):
            try:
                total += os.path.getsize(os.path.join(self.folder, name))
                count += 1
            except OSError:
                pass
        return total, count

    def clear(self):
        size, _ = self.disk_usage()
        for name in os.listdir(self.folder):
            try:
                os.remove(os.path.join(self.folder, name))
            except OSError:
                pass
        self._mem.clear()
        return size
