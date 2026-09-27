# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
import html
import json
import re
import threading
import time
import urllib.parse
import urllib.request

API = "https://api.steampowered.com/ISteamRemoteStorage"
UA = "JModDownloader/2.0 (+https://github.com/Jopseps/Jopseps-mod-manager)"
BATCH = 100
TIMEOUT = 20

# === FILETYPES (GetCollectionDetails children) ===
FILETYPE_ITEM = 0
FILETYPE_COLLECTION = 2

_REQUIRED_BLOCK = re.compile(r'id="RequiredItems"(.*?)</div>\s*</div>', re.S)
_REQUIRED_LINK = re.compile(r'filedetails/\?id=(\d+)"[^>]*>\s*<div class="requiredItem">\s*(.*?)\s*</div>', re.S)


class SteamApiError(Exception):
    pass


class _Throttle:
    """Caps concurrent page scrapes and spaces them out so Steam doesn't rate-limit us."""

    def __init__(self, concurrency=4, min_interval=0.25):
        self._sem = threading.Semaphore(concurrency)
        self._lock = threading.Lock()
        self._next = 0.0
        self._interval = min_interval

    def __enter__(self):
        self._sem.acquire()
        with self._lock:
            now = time.monotonic()
            wait = self._next - now
            self._next = max(now, self._next) + self._interval
        if wait > 0:
            time.sleep(wait)
        return self

    def __exit__(self, *exc):
        self._sem.release()


_scrape_throttle = _Throttle()


def _request(url, data=None):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read()
    except OSError as e:
        raise SteamApiError(f"{url}: {e}") from e


def _post_json(endpoint, form):
    raw = _request(f"{API}/{endpoint}/v1/", form)
    try:
        return json.loads(raw)["response"]
    except (ValueError, KeyError) as e:
        raise SteamApiError(f"{endpoint}: bad response") from e


def _chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def get_details(ids):
    """{id: {title, preview_url, file_size, time_updated, app_id, ok}} for Workshop items (keyless, batched)."""
    out = {}
    for chunk in _chunks(list(ids), BATCH):
        form = {"itemcount": len(chunk)}
        for i, mod_id in enumerate(chunk):
            form[f"publishedfileids[{i}]"] = mod_id
        for entry in _post_json("GetPublishedFileDetails", form).get("publishedfiledetails", []):
            ok = entry.get("result") == 1
            out[entry["publishedfileid"]] = {
                "ok": ok,
                "title": entry.get("title", "") if ok else "",
                "preview_url": entry.get("preview_url", ""),
                "file_size": int(entry.get("file_size") or 0),
                "time_updated": int(entry.get("time_updated") or 0),
                "app_id": int(entry.get("consumer_app_id") or 0),
            }
    return out


def get_collection_children(ids):
    """{id: [(child_id, filetype), ...]} for ids that are collections. Non-collections are omitted."""
    out = {}
    for chunk in _chunks(list(ids), BATCH):
        form = {"collectioncount": len(chunk)}
        for i, mod_id in enumerate(chunk):
            form[f"publishedfileids[{i}]"] = mod_id
        for entry in _post_json("GetCollectionDetails", form).get("collectiondetails", []):
            if entry.get("result") != 1:
                continue
            children = sorted(entry.get("children", []), key=lambda c: c.get("sortorder", 0))
            out[entry["publishedfileid"]] = [(c["publishedfileid"], c.get("filetype", 0)) for c in children]
    return out


def expand_collection(collection_id, children_map=None):
    """Flatten a collection to item ids, recursing into nested collections (visited-safe)."""
    visited = set()
    items = []

    def walk(cid, known):
        if cid in visited:
            return
        visited.add(cid)
        kids = known.get(cid) if known and cid in known else get_collection_children([cid]).get(cid, [])
        for child_id, filetype in kids:
            if filetype == FILETYPE_COLLECTION:
                walk(child_id, None)
            elif child_id not in items:
                items.append(child_id)

    walk(collection_id, children_map)
    return items


def get_required_items(mod_id):
    """[(id, title)] from the item page's Required items box (not exposed by the keyless API)."""
    with _scrape_throttle:
        raw = _request(f"https://steamcommunity.com/sharedfiles/filedetails/?id={mod_id}")
    return parse_required_items(raw.decode("utf-8", "replace"))


def parse_required_items(page):
    block = _REQUIRED_BLOCK.search(page)
    if not block:
        return []
    return [(dep_id, html.unescape(title.strip())) for dep_id, title in _REQUIRED_LINK.findall(block.group(1))]


def search_games(term, limit=10):
    """Store search: [{app_id, name, image}]."""
    query = urllib.parse.urlencode({"term": term, "l": "english", "cc": "US"})
    try:
        data = json.loads(_request(f"https://store.steampowered.com/api/storesearch/?{query}"))
    except ValueError as e:
        raise SteamApiError("store search: bad response") from e
    return [{"app_id": int(item["id"]), "name": item.get("name", ""), "image": item.get("tiny_image", "")}
            for item in data.get("items", []) if item.get("type") == "app"][:limit]


def get_app(app_id):
    """{app_id, name, image} for one AppID via the store appdetails endpoint, or None."""
    query = urllib.parse.urlencode({"appids": app_id, "filters": "basic"})
    try:
        data = json.loads(_request(f"https://store.steampowered.com/api/appdetails?{query}"))
    except ValueError:
        return None
    # Steam sometimes keys the answer by a different id (e.g. 294100 → "1244270"), so take the lone entry
    entry = data.get(str(app_id)) or next(iter(data.values()), {})
    if not entry.get("success"):
        return None
    info = entry.get("data", {})
    return {"app_id": int(app_id), "name": info.get("name", ""), "image": info.get("header_image", "")}


def app_of_item(mod_id):
    """AppID a Workshop item or collection belongs to, or None when Steam doesn't know the item."""
    entry = get_details([mod_id]).get(str(mod_id))
    return entry["app_id"] if entry and entry["ok"] and entry["app_id"] else None


def capsule_url(app_id):
    return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/capsule_184x69.jpg"


def workshop_home(app_id):
    return f"https://steamcommunity.com/app/{app_id}/workshop/"


def fetch_bytes(url):
    return _request(url)
