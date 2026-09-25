import re

_ID_PARAM = re.compile(r"[?&]id=(\d+)")
_BARE_ID = re.compile(r"^\d{3,}$")
_APP_URL = re.compile(r"/app/(\d+)")
_TOKEN_SPLIT = re.compile(r"[\s,;]+")


def extract_mod_id(raw):
    """Workshop ID from a bare number or any steamcommunity URL carrying ?id=."""
    raw = (raw or "").strip()
    match = _ID_PARAM.search(raw)
    if match:
        return match.group(1)
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


def extract_app_id(raw):
    """Steam AppID from a bare number or a store URL like store.steampowered.com/app/294100/..."""
    raw = (raw or "").strip()
    if raw.isdigit():
        return raw
    match = _APP_URL.search(raw)
    if match:
        return match.group(1)
    return None


def workshop_url(mod_id):
    return f"https://steamcommunity.com/sharedfiles/filedetails/?id={mod_id}"
