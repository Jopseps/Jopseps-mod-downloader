"""Flat list models over the queue and the installed records. Rows are painted by delegates.py."""
from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt

from jmd.core.models import Group

NodeRole = Qt.UserRole + 1
DepthRole = Qt.UserRole + 2
KindRole = Qt.UserRole + 3


class QueueModel(QAbstractListModel):
    """Visible rows in order: group headers, items, dependency children (collapsed groups hide their items)."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.ctl = controller
        self.rows = []      # [(node, depth)]
        self.row_of = {}    # mod_id -> row
        controller.queueChanged.connect(self.rebuild)
        controller.itemChanged.connect(self.refresh_item)
        self.rebuild()

    def rebuild(self):
        self.beginResetModel()
        self.rows = []
        self.row_of = {}

        def add_item(item, depth):
            self.row_of[item.id] = len(self.rows)
            self.rows.append((item, depth))
            for dep in item.deps:
                add_item(dep, depth + 1)

        for node in self.ctl.queue.nodes:
            if isinstance(node, Group):
                self.rows.append((node, 0))
                if node.open:
                    for item in node.items:
                        add_item(item, 1)
            else:
                add_item(node, 0)
        self.endResetModel()

    def refresh_item(self, mod_id):
        row = self.row_of.get(mod_id)
        if row is None:
            return
        idx = self.index(row)
        self.dataChanged.emit(idx, idx)
        # a group header's "selected / total" count follows its children
        for r in range(row - 1, -1, -1):
            node, _ = self.rows[r]
            if isinstance(node, Group):
                gi = self.index(r)
                self.dataChanged.emit(gi, gi)
                break
            if self.rows[r][1] == 0:
                break

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        node, depth = self.rows[index.row()]
        if role == NodeRole:
            return node
        if role == DepthRole:
            return depth
        if role == KindRole:
            return "group" if isinstance(node, Group) else "item"
        if role == Qt.DisplayRole:
            return node.title or node.id
        return None


class InstalledModel(QAbstractListModel):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.ctl = controller
        self.rows = []
        controller.installedChanged.connect(self.rebuild)
        self.rebuild()

    def rebuild(self):
        self.beginResetModel()
        recs = list(self.ctl.installed.values())
        # outdated first, then by title
        self.rows = sorted(recs, key=lambda r: (not r.outdated, (r.title or r.id).lower()))
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        rec = self.rows[index.row()]
        if role == NodeRole:
            return rec
        if role == Qt.DisplayRole:
            return rec.title or rec.id
        return None
