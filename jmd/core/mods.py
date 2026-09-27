# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Mod manager state: installed mods (ModEntry), modset references (ModRef), staged active list."""
from dataclasses import asdict, dataclass, field

# === SOURCES ===
JMM = "jmm"          # downloaded by this app
LOCAL = "local"      # dropped into the mod folder by hand
STEAM = "steam"      # Steam client subscription (workshop/content)
BUILTIN = "builtin"  # shipped with the game (RimWorld Core + DLC)


def norm_uid(uid):
    """RimWorld packageIds are case-insensitive, and a Steam copy may carry a '_steam' suffix in ModsConfig."""
    uid = (uid or "").strip().lower()
    return uid[:-6] if uid.endswith("_steam") else uid


@dataclass
class Dep:
    uid: str
    name: str = ""
    wid: str = ""  # Workshop id, so a missing dependency can be downloaded


@dataclass
class ModEntry:
    uid: str
    name: str = ""
    author: str = ""
    source: str = LOCAL
    path: str = ""
    wid: str = ""
    mod_version: str = ""
    supported: list = field(default_factory=list)   # game versions, e.g. ["1.5", "1.6"]
    deps: list = field(default_factory=list)        # [Dep]
    load_after: list = field(default_factory=list)  # [uid]
    load_before: list = field(default_factory=list)
    incompatible: list = field(default_factory=list)
    description: str = ""
    preview: str = ""
    size: int = 0
    toggleable: bool = True  # False: listed only (Steam subscriptions in generic games, Core)

    @property
    def title(self):
        return self.name or self.uid

    def ref(self):
        return ModRef(uid=self.uid, wid=self.wid, name=self.name)


@dataclass
class ModRef:
    """One line of a modset. Either id may be missing: a mod not downloaded yet only has a wid,
    a local or builtin mod only has a uid."""
    uid: str = ""
    wid: str = ""
    name: str = ""

    def matches(self, entry):
        if self.uid and norm_uid(self.uid) == entry.uid:
            return True
        return bool(self.wid) and self.wid == entry.wid

    @classmethod
    def from_dict(cls, data):
        return cls(uid=norm_uid(data.get("uid", "")), wid=str(data.get("wid", "") or ""), name=data.get("name", ""))


@dataclass
class Modset:
    name: str
    mods: list = field(default_factory=list)  # [ModRef], in load order

    def to_dict(self):
        return {"name": self.name, "mods": [asdict(m) for m in self.mods]}

    @classmethod
    def from_dict(cls, data):
        return cls(name=data.get("name", ""), mods=[ModRef.from_dict(m) for m in data.get("mods", [])])


def resolve(refs, entries):
    """Map modset refs onto installed entries. → (active uids in order, missing refs)."""
    by_uid = {e.uid: e for e in entries}
    by_wid = {e.wid: e for e in entries if e.wid}
    active, missing, seen = [], [], set()
    for ref in refs:
        entry = by_uid.get(norm_uid(ref.uid)) if ref.uid else None
        entry = entry or (by_wid.get(ref.wid) if ref.wid else None)
        if entry is None:
            missing.append(ref)
        elif entry.uid not in seen:
            seen.add(entry.uid)
            active.append(entry.uid)
    return active, missing


@dataclass
class Changes:
    added: list
    removed: list
    moved: bool

    @property
    def count(self):
        return len(self.added) + len(self.removed) + (1 if self.moved else 0)


def diff(saved, staged):
    """What Apply would change, for the 'N unsaved changes' label."""
    before, after = set(saved), set(staged)
    added = [u for u in staged if u not in before]
    removed = [u for u in saved if u not in after]
    common_before = [u for u in saved if u in after]
    common_after = [u for u in staged if u in before]
    return Changes(added, removed, common_before != common_after)
