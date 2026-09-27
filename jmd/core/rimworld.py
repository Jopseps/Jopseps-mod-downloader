# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
"""RimWorld file formats: About/About.xml, Config/ModsConfig.xml, Version.txt. Paths come from the caller."""
import os
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET

from jmd.core import ids
from jmd.core.mods import BUILTIN, Dep, ModEntry, norm_uid

APP_ID = 294100
HARMONY = "brrainz.harmony"
CORE = "ludeon.rimworld"
DLCS = ("ludeon.rimworld.royalty", "ludeon.rimworld.ideology", "ludeon.rimworld.biotech",
        "ludeon.rimworld.anomaly", "ludeon.rimworld.odyssey")
_CONFIG_TAIL = os.path.join("Ludeon Studios", "RimWorld by Ludeon Studios", "Config")

_ACTIVE_BLOCK = re.compile(r"([ \t]*)<activeMods>(.*?)</activeMods>", re.S)
_ACTIVE_EMPTY = re.compile(r"([ \t]*)<activeMods\s*/>")
_LI = re.compile(r"<li>\s*([^<]*?)\s*</li>")
_LI_INDENT = re.compile(r"\n([ \t]*)<li>")


def _tag(tag):
    return re.compile(rf"<{tag}>\s*(.*?)\s*</{tag}>", re.S | re.I)


def tier(uid):
    """Pinned load order: Harmony, Core, DLC in release order, then everything else."""
    if uid == HARMONY:
        return 0
    if uid == CORE:
        return 1
    if uid in DLCS:
        return 2 + DLCS.index(uid)
    return 10


def _read(path):
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


# === ABOUT.XML ===
def _text(node, tag):
    child = node.find(tag)
    return (child.text or "").strip() if child is not None and child.text else ""


def _items(node, tag, version):
    """<tag><li>…</li></tag>, preferring <tagByVersion><v1.6>…</v1.6></tagByVersion> for the game version."""
    by_version = node.find(f"{tag}ByVersion")
    if version and by_version is not None:
        vnode = by_version.find(f"v{version}")
        if vnode is not None:
            return vnode.findall("li")
    plain = node.find(tag)
    return plain.findall("li") if plain is not None else []


def _uids(node, tag, version):
    return [norm_uid(li.text) for li in _items(node, tag, version) if li.text and li.text.strip()]


def parse_about(mod_dir, version=""):
    """ModEntry from <mod_dir>/About/About.xml, or None without a packageId. Broken XML falls back to regex."""
    about = os.path.join(mod_dir, "About")
    text = _read(os.path.join(about, "About.xml"))
    if not text:
        return None
    wid = _read(os.path.join(about, "PublishedFileId.txt")).strip()
    folder = os.path.basename(os.path.normpath(mod_dir))
    if not wid.isdigit():
        wid = folder if folder.isdigit() else ""
    preview = os.path.join(about, "Preview.png")
    entry = ModEntry(uid="", path=mod_dir, wid=wid, preview=preview if os.path.isfile(preview) else "")
    try:
        root = ET.fromstring(text.lstrip("﻿").strip())
    except ET.ParseError:
        m = _tag("packageId").search(text)
        if not m:
            return None
        entry.uid = norm_uid(m.group(1))
        name = _tag("name").search(text)
        entry.name = name.group(1).strip() if name else ""
        return entry
    entry.uid = norm_uid(_text(root, "packageId"))
    if not entry.uid:
        return None
    entry.name = _text(root, "name")
    entry.author = _text(root, "author") or ", ".join(
        li.text.strip() for li in _items(root, "authors", "") if li.text)
    entry.mod_version = _text(root, "modVersion")
    entry.description = _text(root, "description")
    entry.supported = [li.text.strip() for li in _items(root, "supportedVersions", "") if li.text]
    for li in _items(root, "modDependencies", version):
        uid = norm_uid(_text(li, "packageId"))
        if uid:
            entry.deps.append(Dep(uid=uid, name=_text(li, "displayName"),
                                  wid=ids.extract_mod_id(_text(li, "steamWorkshopUrl")) or ""))
    entry.load_after = _uids(root, "loadAfter", version) + _uids(root, "forceLoadAfter", version)
    entry.load_before = _uids(root, "loadBefore", version) + _uids(root, "forceLoadBefore", version)
    entry.incompatible = _uids(root, "incompatibleWith", version)
    return entry


def scan_folder(root, source, version=""):
    """Every mod folder directly under root."""
    out = []
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return out
    for name in names:
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            continue
        entry = parse_about(path, version)
        if entry:
            entry.source = source
            out.append(entry)
    return out


def scan_builtin(game_dir, version=""):
    """Core + DLC under <game>/Data. Core can't be switched off."""
    out = scan_folder(os.path.join(game_dir, "Data"), BUILTIN, version) if game_dir else []
    for e in out:
        e.toggleable = e.uid != CORE
    return out


def game_version(game_dir):
    """'1.6.4630 rev467' from <game>/Version.txt, '' when the game isn't there."""
    return _read(os.path.join(game_dir, "Version.txt")).strip() if game_dir else ""


# === MODSCONFIG.XML ===
def config_candidates(steam_libraries=()):
    """Where ModsConfig.xml may live: native Linux/Windows/macOS, then Proton prefixes."""
    home = os.path.expanduser("~")
    out = []
    if sys.platform == "win32":
        out.append(os.path.join(os.environ.get("USERPROFILE", home), "AppData", "LocalLow", _CONFIG_TAIL))
    elif sys.platform == "darwin":
        out.append(os.path.join(home, "Library", "Application Support", "RimWorld", "Config"))
    else:
        out.append(os.path.join(home, ".config", "unity3d", _CONFIG_TAIL))
        for lib in steam_libraries:
            out.append(os.path.join(lib, "steamapps", "compatdata", str(APP_ID), "pfx", "drive_c", "users",
                                    "steamuser", "AppData", "LocalLow", _CONFIG_TAIL))
    return [os.path.join(c, "ModsConfig.xml") for c in out]


def find_config(steam_libraries=()):
    for path in config_candidates(steam_libraries):
        if os.path.isfile(path):
            return path
    return ""


def read_active(path):
    """Active packageIds from ModsConfig.xml, as written (may carry '_steam'). [] when missing."""
    m = _ACTIVE_BLOCK.search(_read(path))
    return [li for li in _LI.findall(m.group(2)) if li] if m else []


def write_active(path, raw_ids):
    """Replace only <activeMods>. <version>, <knownExpansions> and everything else stay byte-for-byte."""
    text = _read(path)
    if not text:
        text = "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<ModsConfigData>\n  <activeMods />\n</ModsConfigData>\n"
    m = _ACTIVE_BLOCK.search(text) or _ACTIVE_EMPTY.search(text)
    indent = m.group(1) if m else "  "
    li_indent = indent + "  "
    if m and m.re is _ACTIVE_BLOCK:
        inner = _LI_INDENT.search(m.group(2))
        if inner:
            li_indent = inner.group(1)
    lines = "".join(f"\n{li_indent}<li>{uid}</li>" for uid in raw_ids)
    block = f"{indent}<activeMods>{lines}\n{indent}</activeMods>"
    if m:
        text = text[:m.start()] + block + text[m.end():]
    else:
        text = text.replace("</ModsConfigData>", f"{block}\n</ModsConfigData>", 1)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, path)


def backup(path, folder, keep=10):
    """Timestamped copy of ModsConfig.xml, keeping the newest `keep`. → backup path or ''."""
    if not os.path.isfile(path):
        return ""
    os.makedirs(folder, exist_ok=True)
    dst = os.path.join(folder, time.strftime("ModsConfig-%Y%m%d-%H%M%S.xml"))
    shutil.copy2(path, dst)
    old = sorted(f for f in os.listdir(folder) if f.startswith("ModsConfig-") and f.endswith(".xml"))
    for name in old[:-keep]:
        try:
            os.remove(os.path.join(folder, name))
        except OSError:
            pass
    return dst
