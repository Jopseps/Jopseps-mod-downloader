# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tabletop Simulator: Workshop saves come from SteamCMD as one BSON file (<hash>_legacy.bin); TTS reads
Mods/Workshop/<id>.json and lists what WorkshopFileInfos.json names."""
import base64
import json
import os
import re
import struct
import sys
import time

APP_ID = 286160
INFOS = "WorkshopFileInfos.json"
_SAVE_NAME = re.compile(rb'"SaveName"\s*:\s*"((?:[^"\\]|\\.)*)"')


class TtsError(Exception):
    pass


# === BSON ===
def _cstring(data, i):
    end = data.index(b"\x00", i)
    return data[i:end].decode("utf-8", "replace"), end + 1


def _string(data, i):
    (n,) = struct.unpack_from("<i", data, i)
    return data[i + 4:i + 4 + n - 1].decode("utf-8", "replace"), i + 4 + n


def _document(data, i, as_list=False):
    (size,) = struct.unpack_from("<i", data, i)
    end = i + size - 1
    i += 4
    out = []
    while i < end:
        kind = data[i]
        key, i = _cstring(data, i + 1)
        if kind == 0x01:
            (val,) = struct.unpack_from("<d", data, i)
            i += 8
        elif kind in (0x02, 0x0D, 0x0E):  # string, JS code, symbol
            val, i = _string(data, i)
        elif kind in (0x03, 0x04):
            val, i = _document(data, i, kind == 0x04)
        elif kind == 0x05:
            (n,) = struct.unpack_from("<i", data, i)
            val = base64.b64encode(data[i + 5:i + 5 + n]).decode("ascii")  # how Newtonsoft writes byte[]
            i += 5 + n
        elif kind == 0x07:
            val = data[i:i + 12].hex()
            i += 12
        elif kind == 0x08:
            val = data[i] != 0
            i += 1
        elif kind in (0x06, 0x0A):  # undefined, null
            val = None
        elif kind == 0x09:
            (val,) = struct.unpack_from("<q", data, i)
            i += 8
        elif kind == 0x10:
            (val,) = struct.unpack_from("<i", data, i)
            i += 4
        elif kind in (0x11, 0x12):
            (val,) = struct.unpack_from("<q", data, i)
            i += 8
        else:
            raise TtsError(f"Unsupported BSON type 0x{kind:02x} at byte {i}")
        out.append((key, val))
    if as_list:
        return [v for _, v in out], end + 1
    return dict(out), end + 1


def bson_loads(data):
    try:
        doc, _ = _document(data, 0)
    except (struct.error, ValueError, IndexError) as e:
        raise TtsError(f"Broken BSON: {e}") from e
    return doc


def load_save(path):
    """A Workshop save as a dict: BSON, or JSON text for the few uploaded that way."""
    with open(path, "rb") as f:
        data = f.read()
    # BSON opens with its own length; a first byte of '{' alone could be a length ending in 0x7B
    if len(data) >= 5 and struct.unpack_from("<i", data)[0] == len(data):
        return bson_loads(data)
    try:
        return json.loads(data.decode("utf-8-sig"))
    except ValueError as e:
        raise TtsError(f"Neither BSON nor JSON: {path}") from e


def legacy_file(content_path):
    """The save inside a SteamCMD content folder (or the file itself)."""
    if os.path.isfile(content_path):
        return content_path
    try:
        names = sorted(os.listdir(content_path))
    except OSError:
        names = []
    files = [n for n in names if os.path.isfile(os.path.join(content_path, n))]
    pick = next((n for n in files if n.endswith("_legacy.bin")), None) or (files[0] if len(files) == 1 else None)
    if not pick:
        raise TtsError(f"No save file in {content_path}")
    return os.path.join(content_path, pick)


def _write_atomic(path, text, newline="\n"):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline=newline) as f:
        f.write(text)
    os.replace(tmp, path)


def write_save(src, dst, title="", time_updated=0):
    """Convert a Workshop save to the pretty JSON TTS keeps in Mods/Workshop. → the save dict
    Fills what TTS fills when it subscribes: an empty SaveName gets the title, EpochTime the Steam time."""
    save = load_save(src)
    if save.get("SaveName") in (None, "", "None") and title:  # Unity wrote a null name as "None"
        save["SaveName"] = title
    if "EpochTime" not in save and time_updated:
        items = list(save.items())
        at = next((n + 1 for n, (k, _) in enumerate(items) if k == "SaveName"), 0)
        items.insert(at, ("EpochTime", int(time_updated)))
        save = dict(items)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    _write_atomic(dst, json.dumps(save, indent=2, ensure_ascii=False))
    return save


def save_name(path):
    """SaveName from the head of a <id>.json, without parsing a 20 MB file."""
    try:
        with open(path, "rb") as f:
            m = _SAVE_NAME.search(f.read(4096))
        return json.loads(b'"' + m.group(1) + b'"') if m else ""
    except (OSError, ValueError):
        return ""


# === WorkshopFileInfos.json ===
def read_infos(folder):
    try:
        with open(os.path.join(folder, INFOS), "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return [e for e in data if isinstance(e, dict)] if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def write_infos(folder, infos):
    os.makedirs(folder, exist_ok=True)
    # TTS writes it with CRLF on every OS
    _write_atomic(os.path.join(folder, INFOS), json.dumps(infos, indent=2, ensure_ascii=False), newline="\r\n")


def entry_id(entry):
    """'…\\Workshop\\123.json' → '123'. TTS mixes / and \\ in Directory, so only the file name counts."""
    name = re.split(r"[\\/]", str(entry.get("Directory", "")))[-1]
    return name[:-5] if name.lower().endswith(".json") else name


def _directory(folder, infos, mod_id):
    """Same prefix style as the entries TTS wrote, so both point at the same place."""
    for e in infos:
        d = str(e.get("Directory", ""))
        cut = max(d.rfind("\\"), d.rfind("/"))
        if cut > 0:
            return d[:cut + 1] + f"{mod_id}.json"
    return os.path.join(folder, f"{mod_id}.json")


def find_info(infos, mod_id):
    return next((e for e in infos if entry_id(e) == mod_id), None)


def upsert_info(folder, mod_id, name, update_time=None, keep=None):
    """Add or refresh a mod's entry; keep = an entry saved while it was off (keeps TTS's own fields)."""
    infos = read_infos(folder)
    entry = find_info(infos, mod_id)
    if entry is None:
        entry = dict(keep) if keep else {}
        infos.append(entry)
    entry["Directory"] = _directory(folder, [e for e in infos if e is not entry], mod_id)
    if name or "Name" not in entry:
        entry["Name"] = name or entry.get("Name", "") or mod_id
    # TTS stores when it wrote the file, not Steam's time_updated
    entry["UpdateTime"] = int(update_time if update_time is not None else entry.get("UpdateTime") or time.time())
    write_infos(folder, infos)
    return entry


def drop_info(folder, mod_id):
    """Remove a mod's entry. → the removed entry or None"""
    infos = read_infos(folder)
    entry = find_info(infos, mod_id)
    if entry is not None:
        infos.remove(entry)
        write_infos(folder, infos)
    return entry


# === FOLDERS ===
def documents_dir():
    """The user's Documents, following OneDrive / localized redirects on Windows."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                            ("Data4", ctypes.c_ubyte * 8)]

            # FOLDERID_Documents {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
            fid = GUID(0xFDD39AD0, 0x238F, 0x46AF, (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
            out = ctypes.c_wchar_p()
            shell32 = ctypes.windll.shell32
            if shell32.SHGetKnownFolderPath(ctypes.byref(fid), 0, None, ctypes.byref(out)) == 0:
                path = out.value
                ctypes.windll.ole32.CoTaskMemFree(out)
                if path:
                    return path
        except (OSError, AttributeError):
            pass
        return os.path.join(os.path.expanduser("~"), "Documents")
    return os.path.expanduser("~")


def default_workshop_dir():
    if sys.platform == "win32":
        return os.path.join(documents_dir(), "My Games", "Tabletop Simulator", "Mods", "Workshop")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Tabletop Simulator/Mods/Workshop")
    return os.path.expanduser("~/.local/share/Tabletop Simulator/Mods/Workshop")
