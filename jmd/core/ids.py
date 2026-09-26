# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
import re

_ID_PARAM = re.compile(r"[?&]id=(\d+)|CommunityFilePage/(\d+)")
_BARE_ID = re.compile(r"^\d{3,}$")
_APP_URL = re.compile(r"/app/(\d+)|[?&]appid=(\d+)|steam://(?:store|run|rungameid)/(\d+)")
_TOKEN_SPLIT = re.compile(r"[\s,;]+")


def extract_mod_id(raw):
    """Workshop ID from a bare number, any steamcommunity URL carrying ?id=, or a steam:// CommunityFilePage link."""
    raw = (raw or "").strip()
    match = _ID_PARAM.search(raw)
    if match:
        return match.group(1) or match.group(2)
    if _BARE_ID.match(raw):
        return raw
    return None


def extract_ids(text):
    """All Workshop IDs in pasted text (one or many, any separator), order kept, no dupes."""
    seen = set()
    ids = []
    for token in _TOKEN_SPLIT.split(text or ""):
        mod_id = extract_mod_id(token)
        if mod_id and mod_id not in seen:
            seen.add(mod_id)
            ids.append(mod_id)
    return ids


def parse_game_ref(raw):
    """What a pasted game reference points at: ("app", id) for an AppID, a store/community/Workshop browse link,
    ("item", id) for a Workshop item or collection link (its game is looked up), None otherwise."""
    raw = (raw or "").strip()
    if raw.isdigit():
        return ("app", raw)
    match = _APP_URL.search(raw)
    if match:
        return ("app", next(g for g in match.groups() if g))
    match = _ID_PARAM.search(raw)
    if match:
        return ("item", match.group(1) or match.group(2))
    return None


def workshop_url(mod_id):
    return f"https://steamcommunity.com/sharedfiles/filedetails/?id={mod_id}"
