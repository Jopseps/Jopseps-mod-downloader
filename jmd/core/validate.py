# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Problems with a staged active list. Warnings only: nothing here blocks Apply."""
from dataclasses import dataclass, field

ERROR = "error"
WARN = "warn"

MISSING_DEP = "missing_dep"      # not installed at all → download
INACTIVE_DEP = "inactive_dep"    # installed but not active → activate
ORDER = "order"
INCOMPATIBLE = "incompatible"
VERSION = "version"
DUPLICATE = "duplicate"
CYCLE = "cycle"
NOT_INSTALLED = "not_installed"  # in the active list, but no such mod on disk


@dataclass
class Issue:
    level: str
    kind: str
    uid: str
    text: str
    fix: list = field(default_factory=list)  # uids to activate, or Workshop ids to download (MISSING_DEP)


def short_version(text):
    """'1.6.4630 rev467' → '1.6'."""
    parts = (text or "").strip().split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 and parts[0].isdigit() else ""


def check(active, entries, game_version="", check_order=True, duplicates=(), cycles=(), tier=lambda uid: 0):
    """active: staged uids in order. entries: {uid: ModEntry} for everything installed.
    Order rules that fight a pinned tier (something 'loadBefore' Core) are ignored, as in sorting."""
    issues = []
    pos = {u: i for i, u in enumerate(active)}
    version = short_version(game_version)
    pairs = set()

    def name(uid):
        e = entries.get(uid)
        return e.title if e else uid

    top = None  # highest pinned tier seen so far, for 'Harmony after Core'
    for uid in active:
        e = entries.get(uid)
        if not e:
            issues.append(Issue(WARN, NOT_INSTALLED, uid, "Active but not installed"))
            continue
        if check_order and top is not None and tier(uid) < tier(top):
            issues.append(Issue(WARN, ORDER, uid, f"Should load before {name(top)}"))
        if top is None or tier(uid) > tier(top):
            top = uid
        for dep in e.deps:
            if dep.uid not in entries:
                fix = [dep.wid] if dep.wid else []
                issues.append(Issue(ERROR, MISSING_DEP, uid, f"Requires {dep.name or dep.uid}, which isn't installed", fix))
            elif dep.uid not in pos:
                issues.append(Issue(ERROR, INACTIVE_DEP, uid, f"Requires {name(dep.uid)}, which isn't active", [dep.uid]))
            elif check_order and pos[dep.uid] > pos[uid] and tier(dep.uid) <= tier(uid):
                issues.append(Issue(WARN, ORDER, uid, f"Should load after {name(dep.uid)}"))
        if check_order:
            for other in e.load_after:
                if other in pos and pos[other] > pos[uid] and tier(other) <= tier(uid):
                    issues.append(Issue(WARN, ORDER, uid, f"Should load after {name(other)}"))
            for other in e.load_before:
                if other in pos and pos[other] < pos[uid] and tier(uid) <= tier(other):
                    issues.append(Issue(WARN, ORDER, uid, f"Should load before {name(other)}"))
        for other in e.incompatible:
            pair = frozenset((uid, other))
            if other in pos and other != uid and pair not in pairs:
                pairs.add(pair)
                issues.append(Issue(ERROR, INCOMPATIBLE, uid, f"Incompatible with {name(other)}"))
        if version and e.supported and version not in e.supported:
            issues.append(Issue(WARN, VERSION, uid, f"Made for {', '.join(e.supported)}, game is {version}"))

    for uid in duplicates:
        if uid in pos:
            issues.append(Issue(WARN, DUPLICATE, uid, f"{name(uid)} is installed more than once"))
    for comp in cycles:
        names = ", ".join(name(u) for u in comp)
        issues.append(Issue(WARN, CYCLE, comp[0], f"Load order rules loop between {names}. Kept your order."))
    return issues
