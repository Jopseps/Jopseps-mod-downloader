# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Inactive / Active columns of the Manage view: filtered list model with drag & drop, compact painted rows."""
from PySide6.QtCore import QAbstractListModel, QMimeData, QModelIndex, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics
from PySide6.QtWidgets import QAbstractItemView, QFrame, QListView, QStyle, QStyledItemDelegate

from jmd.core import mods, validate
from jmd.ui import icons
from jmd.ui.delegates import draw_thumb, elide, font, initials, rounded
from jmd.ui.tokens import C, FONT_MONO, STATUS

UidRole = Qt.UserRole + 1
MIME = "application/x-jmm-uids"
ROW_H = 32

F_NAME = font(13, QFont.Medium)
F_NUM = font(11, family=FONT_MONO)
F_TAG = font(10, QFont.Bold)

# source → (label, fg, bg) for the little badge; JMM mods carry none
BADGES = {
    mods.STEAM: ("STEAM", C["steam-blue"], "#17324a"),
    mods.LOCAL: ("LOCAL", C["text-dim"], C["btn-secondary"]),
    mods.BUILTIN: ("GAME", STATUS["done"][1], STATUS["done"][2]),
}


class ModListModel(QAbstractListModel):
    def __init__(self, mgr, side, parent=None):
        super().__init__(parent)
        self.mgr = mgr
        self.side = side  # "active" | "inactive"
        self.rows = []
        self.filter = ""
        mgr.changed.connect(self.rebuild)
        mgr.stagedChanged.connect(self.rebuild)
        self.rebuild()

    @property
    def is_active(self):
        return self.side == "active"

    def all_uids(self):
        return self.mgr.staged if self.is_active else self.mgr.inactive()

    def rebuild(self):
        self.beginResetModel()
        needle = self.filter.lower()
        uids = self.all_uids()
        if needle:
            uids = [u for u in uids if needle in self.mgr.title(u).lower() or needle in u]
        self.rows = list(uids)
        self.endResetModel()

    def set_filter(self, text):
        self.filter = text.strip()
        self.rebuild()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        uid = self.rows[index.row()]
        if role == UidRole:
            return uid
        if role == Qt.DisplayRole:
            return self.mgr.title(uid)
        if role == Qt.ToolTipRole:
            issues = self.mgr.issues_for(uid) if self.is_active else []
            return "\n".join(i.text for i in issues) or None
        return None

    def position(self, uid):
        """1-based load position in the full active list (the view may be filtered)."""
        try:
            return self.mgr.staged.index(uid) + 1
        except ValueError:
            return 0

    # === DRAG & DROP ===
    def flags(self, index):
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled
        return base if index.isValid() else Qt.ItemIsDropEnabled

    def supportedDropActions(self):
        return Qt.MoveAction

    def mimeTypes(self):
        return [MIME]

    def mimeData(self, indexes):
        data = QMimeData()
        uids = [self.rows[i.row()] for i in sorted(indexes, key=lambda i: i.row())]
        data.setData(MIME, "\n".join(uids).encode())
        return data

    def canDropMimeData(self, data, action, row, column, parent):
        return data.hasFormat(MIME)

    def dropMimeData(self, data, action, row, column, parent):
        if not data.hasFormat(MIME):
            return False
        uids = [u for u in bytes(data.data(MIME)).decode().split("\n") if u]
        if self.is_active:
            if row < 0 and parent.isValid():
                row = parent.row()
            before = self.rows[row] if 0 <= row < len(self.rows) else None
            self.mgr.activate(uids, before)
        else:
            self.mgr.deactivate([u for u in uids if u in self.mgr.staged])
        # the manager already moved them; returning False keeps Qt from removing source rows
        return False


class ModDelegate(QStyledItemDelegate):
    def __init__(self, mgr, thumbs, side, parent=None):
        super().__init__(parent)
        self.mgr = mgr
        self.thumbs = thumbs
        self.side = side

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), ROW_H)

    def paint(self, p, option, index):
        uid = index.data(UidRole)
        mgr = self.mgr
        entry = mgr.by_uid.get(uid)
        r = option.rect
        p.save()
        p.setRenderHint(p.RenderHint.Antialiasing)
        if option.state & QStyle.State_Selected:
            p.fillRect(r, QColor(C["row-selected"]))
            p.fillRect(QRect(r.left(), r.top(), 2, r.height()), QColor(C["accent"]))
        elif option.state & QStyle.State_MouseOver:
            p.fillRect(r, QColor(C["row-hover"]))
        p.fillRect(QRect(r.left(), r.bottom(), r.width(), 1), QColor(C["divider"]))

        cy = r.center().y() + 1
        x = r.left() + 10
        if self.side == "active" and mgr.ordered:
            p.setFont(F_NUM)
            p.setPen(QColor(C["text-faint"]))
            p.drawText(QRect(x - 4, r.top(), 26, r.height()), Qt.AlignRight | Qt.AlignVCenter,
                       str(index.model().position(uid)))
            x += 30
        thumb = QRect(x, cy - 11, 22, 22)
        pm = self.thumbs.get_any(f"mod_{uid}", entry.preview) if entry and entry.preview else None
        draw_thumb(p, thumb, pm, uid, initials(mgr.title(uid))[:1] if not pm else "")
        x = thumb.right() + 10

        # === RIGHT SIDE (right to left) ===
        right = r.right() - 10
        if entry is None:
            right = self._badge(p, right, cy, "MISSING", STATUS["failed"][1], STATUS["failed"][2])
        else:
            if mgr.pinned(uid):
                right -= 14
                icons.paint(p, "pin", QRect(right, cy - 7, 14, 14), C["text-faint"], 2.0)
                right -= 6
            elif not entry.toggleable:
                right -= 14
                icons.paint(p, "lock", QRect(right, cy - 7, 14, 14), C["text-faint"], 2.0)
                right -= 6
            pct = mgr.update_progress(uid)
            if pct is not None:
                right = self._badge(p, right, cy, f"{int(pct)}%", C["steam-blue"], "#17324a")
            elif mgr.outdated(uid):
                right -= 15
                icons.paint(p, "refresh", QRect(right, cy - 7, 15, 15), STATUS["outdated"][1], 2.2)
                right -= 6
            if self.side == "active":
                issues = mgr.issues_for(uid)
                if issues:
                    worst = validate.ERROR if any(i.level == validate.ERROR for i in issues) else validate.WARN
                    color = STATUS["failed"][1] if worst == validate.ERROR else STATUS["outdated"][1]
                    right -= 15
                    icons.paint(p, "warn", QRect(right, cy - 7, 15, 15), color, 2.2)
                    right -= 6
            badge = BADGES.get(entry.source)
            if badge:
                right = self._badge(p, right, cy, *badge)

        p.setFont(F_NAME)
        missing = entry is None
        p.setPen(QColor(C["danger-text"] if missing else C["text-strong"] if option.state & QStyle.State_Selected
                        else C["text"]))
        p.drawText(QRect(x, r.top(), right - x - 8, r.height()), Qt.AlignLeft | Qt.AlignVCenter,
                   elide(mgr.title(uid), QFontMetrics(F_NAME), right - x - 8))
        p.restore()

    def _badge(self, p, right, cy, text, fg, bg):
        fm = QFontMetrics(F_TAG)
        w = fm.horizontalAdvance(text) + 10
        rect = QRect(right - w, cy - 8, w, 16)
        rounded(p, rect, 3, bg)
        p.setFont(F_TAG)
        p.setPen(QColor(fg))
        p.drawText(rect, Qt.AlignCenter, text)
        return rect.left() - 8


class ModListView(QListView):
    """Extended selection, drag within and across columns, Enter / double-click switches side."""
    toggled = Signal(list)       # uids to move to the other column
    current = Signal(str)        # focused uid for the details panel
    deleteRequested = Signal(list)

    def __init__(self, model, delegate, parent=None):
        super().__init__(parent)
        self.setModel(model)
        self.setItemDelegate(delegate)
        delegate.setParent(self)
        self.setMouseTracking(True)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)
        self.setVerticalScrollMode(QListView.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self._keep = []
        model.modelAboutToBeReset.connect(lambda: setattr(self, "_keep", self.selected_uids()))
        model.modelReset.connect(self._restore)
        self.doubleClicked.connect(lambda idx: self.toggled.emit([idx.data(UidRole)]))

    def selected_uids(self):
        rows = sorted(i.row() for i in self.selectionModel().selectedIndexes()) if self.selectionModel() else []
        return [self.model().rows[r] for r in rows if r < len(self.model().rows)]

    def select_uids(self, uids, scroll=True):
        sm = self.selectionModel()
        sm.clearSelection()
        first = None
        for uid in uids:
            if uid in self.model().rows:
                idx = self.model().index(self.model().rows.index(uid))
                sm.select(idx, sm.SelectionFlag.Select)
                first = first or idx
        if first is not None:
            sm.setCurrentIndex(first, sm.SelectionFlag.NoUpdate)
            if scroll:
                self.scrollTo(first)

    def _restore(self):
        if self._keep:
            self.select_uids(self._keep, scroll=False)

    def currentChanged(self, cur, prev):
        super().currentChanged(cur, prev)
        if cur.isValid():
            self.current.emit(cur.data(UidRole))

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            uids = self.selected_uids()
            if uids:
                self.toggled.emit(uids)
            return
        if e.key() == Qt.Key_Delete:
            uids = self.selected_uids()
            if uids:
                self.deleteRequested.emit(uids)
            return
        super().keyPressEvent(e)
