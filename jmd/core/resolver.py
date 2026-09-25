from jmd.core import steam_api


def classify(ids):
    """Split pasted/added ids into collections (expanded, titled) and plain items.
    Returns ([(collection_id, title, [item_ids])], [plain_ids]). Blocking; call from a worker."""
    children = steam_api.get_collection_children(ids)
    collections = []
    if children:
        titles = steam_api.get_details(list(children))
        for cid in ids:
            if cid in children:
                title = titles.get(cid, {}).get("title") or f"Collection {cid}"
                collections.append((cid, title, steam_api.expand_collection(cid, children)))
    plain = [i for i in ids if i not in children]
    return collections, plain


def details(ids):
    return steam_api.get_details(ids)


def required(mod_id):
    """[(dep_id, dep_title)] for one item; [] when the page can't be read."""
    try:
        return steam_api.get_required_items(mod_id)
    except steam_api.SteamApiError:
        return []
