import json
import os
import re
from dataclasses import asdict

from jmd import paths
from jmd.core.models import InstalledRecord, Profile, QueueState, Settings


def _read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write_json(path, data):
    """Atomic write: temp file + replace, so a crash never leaves half a file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _safe_name(name):
    return re.sub(r"[^\w\- .]+", "_", name).strip() or "list"


class Store:
    """JSON persistence under the app data dir: settings, profiles, per-profile queue/lists/installed."""

    def __init__(self, root=None):
        self.root = root or paths.data_dir()

    def _path(self, *parts):
        return os.path.join(self.root, *parts)

    # === SETTINGS ===
    def load_settings(self):
        data = _read_json(self._path("settings.json"), {})
        known = {k: v for k, v in data.items() if k in Settings.__dataclass_fields__}
        return Settings(**known)

    def save_settings(self, settings):
        _write_json(self._path("settings.json"), asdict(settings))

    # === PROFILES ===
    def load_profiles(self):
        data = _read_json(self._path("profiles.json"), [])
        profiles = []
        for entry in data:
            known = {k: v for k, v in entry.items() if k in Profile.__dataclass_fields__}
            profiles.append(Profile(**known))
        return profiles

    def save_profiles(self, profiles):
        _write_json(self._path("profiles.json"), [asdict(p) for p in profiles])

    # === QUEUE ===
    def load_queue(self, profile_id):
        return QueueState.from_list(_read_json(self._path("profiles", profile_id, "queue.json"), []))

    def save_queue(self, profile_id, queue):
        _write_json(self._path("profiles", profile_id, "queue.json"), queue.to_list())

    # === NAMED LISTS ===
    def list_names(self, profile_id):
        folder = self._path("profiles", profile_id, "lists")
        if not os.path.isdir(folder):
            return []
        return sorted(f[:-5] for f in os.listdir(folder) if f.endswith(".json"))

    def save_list(self, profile_id, name, queue):
        _write_json(self._path("profiles", profile_id, "lists", _safe_name(name) + ".json"),
                    {"name": name, "nodes": queue.to_list()})

    def load_list(self, profile_id, name):
        data = _read_json(self._path("profiles", profile_id, "lists", _safe_name(name) + ".json"), None)
        if data is None:
            return None
        return QueueState.from_list(data.get("nodes", []))

    def delete_list(self, profile_id, name):
        try:
            os.remove(self._path("profiles", profile_id, "lists", _safe_name(name) + ".json"))
        except OSError:
            pass

    # === INSTALLED ===
    def load_installed(self, profile_id):
        data = _read_json(self._path("profiles", profile_id, "installed.json"), {})
        records = {}
        for mod_id, entry in data.items():
            known = {k: v for k, v in entry.items() if k in InstalledRecord.__dataclass_fields__}
            records[mod_id] = InstalledRecord(**known)
        return records

    def save_installed(self, profile_id, records):
        _write_json(self._path("profiles", profile_id, "installed.json"),
                    {mod_id: asdict(rec) for mod_id, rec in records.items()})
