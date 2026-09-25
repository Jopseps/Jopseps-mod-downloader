import re
import time
from dataclasses import asdict, dataclass, field

# === STATUSES ===
RESOLVING = "resolving"
QUEUED = "queued"
DOWNLOADING = "downloading"
RETRYING = "retrying"
DONE = "done"
FAILED = "failed"
LOGIN = "login"
OUTDATED = "outdated"
SKIPPED = "skipped"  # derived: unchecked + queued, never stored

FINISHED = {DONE}
ACTIVE = {DOWNLOADING, RETRYING}


@dataclass
class ModItem:
    id: str
    title: str = ""
    preview_url: str = ""
    file_size: int = 0
    time_updated: int = 0
    app_id: int = 0
    status: str = RESOLVING
    checked: bool = True
    required_by: str = ""
    deps: list = field(default_factory=list)
    attempt: int = 0
    error: str = ""
    progress: float = 0.0
    blocked: bool = False  # permanent failure (removed / other game): never downloadable

    @property
    def display_status(self):
        if not self.checked and self.status == QUEUED:
            return SKIPPED
        return self.status

    def to_dict(self):
        data = asdict(self)
        data["deps"] = [dep.to_dict() for dep in self.deps]
        # transient download state is not persisted
        if data["status"] in (DOWNLOADING, RETRYING):
            data["status"] = QUEUED
        data["progress"] = 0.0
        data["attempt"] = 0
        return data

    @classmethod
    def from_dict(cls, data):
        data = dict(data)
        deps = [cls.from_dict(dep) for dep in data.pop("deps", [])]
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        item = cls(**known)
        item.deps = deps
        return item


@dataclass
class Group:
    id: str
    title: str = ""
    items: list = field(default_factory=list)
    open: bool = True

    def to_dict(self):
        return {"kind": "group", "id": self.id, "title": self.title, "open": self.open,
                "items": [item.to_dict() for item in self.items]}

    @classmethod
    def from_dict(cls, data):
        return cls(id=data["id"], title=data.get("title", ""), open=data.get("open", True),
                   items=[ModItem.from_dict(item) for item in data.get("items", [])])


@dataclass
class Profile:
    id: str
    name: str
    app_id: int
    mod_dir: str = ""
    sync_mode: str = "copy"  # copy | link
    handler: str = "generic"
    capsule_url: str = ""

    @staticmethod
    def slug_for(name, app_id):
        base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "game"
        return f"{base}-{app_id}"


@dataclass
class Settings:
    steamcmd_path: str = ""
    cache_mode: str = "app"  # app | existing
    retries: int = 3
    username: str = ""
    current_profile: str = ""
    onboarded: bool = False


@dataclass
class InstalledRecord:
    id: str
    title: str = ""
    preview_url: str = ""
    file_size: int = 0
    time_updated: int = 0
    synced_at: int = 0
    remote_updated: int = 0  # latest time_updated seen on Steam

    @property
    def outdated(self):
        return self.remote_updated > self.time_updated

    @classmethod
    def from_item(cls, item):
        return cls(id=item.id, title=item.title, preview_url=item.preview_url, file_size=item.file_size,
                   time_updated=item.time_updated, synced_at=int(time.time()), remote_updated=item.time_updated)


class QueueState:
    """The left-panel queue: top-level items and collection groups; items may carry dependency children."""

    def __init__(self, nodes=None):
        self.nodes = nodes or []

    # === LOOKUP ===
    def iter_items(self):
        """Yield (item, depth, parent) depth-first over every ModItem."""
        def walk(item, depth, parent):
            yield item, depth, parent
            for dep in item.deps:
                yield from walk(dep, depth + 1, item)

        for node in self.nodes:
            if isinstance(node, Group):
                for item in node.items:
                    yield from walk(item, 1, node)
            else:
                yield from walk(node, 0, None)

    def items(self):
        return [item for item, _, _ in self.iter_items()]

    def find(self, mod_id):
        for item, _, _ in self.iter_items():
            if item.id == mod_id:
                return item
        return None

    def has(self, mod_id):
        return self.find(mod_id) is not None or any(
            isinstance(node, Group) and node.id == mod_id for node in self.nodes)

    def group(self, group_id):
        for node in self.nodes:
            if isinstance(node, Group) and node.id == group_id:
                return node
        return None

    def parent_of(self, target):
        for item, _, parent in self.iter_items():
            if item is target:
                return parent
        return None

    # === MUTATION ===
    def add_item(self, mod_id):
        if self.has(mod_id):
            return None
        item = ModItem(id=mod_id)
        self.nodes.append(item)
        return item

    def add_group(self, group_id, title, child_ids):
        if self.group(group_id):
            return None
        group = Group(id=group_id, title=title)
        for child_id in child_ids:
            if not self.has(child_id) and not any(i.id == child_id for i in group.items):
                group.items.append(ModItem(id=child_id))
        self.nodes.append(group)
        return group

    def add_dep(self, parent, mod_id, dep_title=""):
        if self.has(mod_id):
            return None
        dep = ModItem(id=mod_id, title=dep_title, required_by=parent.title or parent.id)
        parent.deps.append(dep)
        return dep

    def remove(self, target):
        if isinstance(target, Group):
            self.nodes = [node for node in self.nodes if node is not target]
            return
        if target in self.nodes:
            self.nodes.remove(target)
            return
        parent = self.parent_of(target)
        if isinstance(parent, Group):
            parent.items.remove(target)
        elif parent is not None:
            parent.deps.remove(target)

    def remove_id(self, mod_id):
        group = self.group(mod_id)
        if group:
            self.remove(group)
            return True
        item = self.find(mod_id)
        if item:
            self.remove(item)
            return True
        return False

    def clear(self):
        self.nodes = []

    # === COUNTS ===
    def pending(self):
        """Items the Download button would fetch."""
        return [i for i in self.items()
                if i.checked and not i.blocked and i.status in (QUEUED, FAILED, RETRYING, LOGIN)]

    def count(self, status):
        return sum(1 for i in self.items() if i.status == status)

    # === PERSISTENCE ===
    def to_list(self):
        return [node.to_dict() for node in self.nodes]

    @classmethod
    def from_list(cls, data):
        nodes = []
        for entry in data or []:
            if entry.get("kind") == "group":
                nodes.append(Group.from_dict(entry))
            else:
                nodes.append(ModItem.from_dict(entry))
        return cls(nodes)
