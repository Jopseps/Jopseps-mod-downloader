# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
import filecmp
import os
import shutil
import sys

IS_WIN = sys.platform == "win32"


class SyncError(Exception):
    pass


def is_link(path):
    """Symlink, or a Windows junction."""
    if os.path.islink(path):
        return True
    if IS_WIN and os.path.isdir(path):
        try:
            return bool(os.readlink(path))
        except OSError:
            return False
    return False


def _unlink(path):
    if IS_WIN and os.path.isdir(path) and not os.path.islink(path):
        os.rmdir(path)  # junction: rmdir removes the link, not the target
    else:
        os.unlink(path)


def mirror_copy(src, dst):
    """Make dst an exact copy of src: copy new/changed files, delete files that vanished upstream."""
    if not os.path.isdir(src):
        raise SyncError(f"Source missing: {src}")
    if is_link(dst):
        _unlink(dst)
    os.makedirs(dst, exist_ok=True)

    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        target_root = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(target_root, exist_ok=True)
        for name in files:
            s = os.path.join(root, name)
            d = os.path.join(target_root, name)
            if not os.path.exists(d) or not filecmp.cmp(s, d, shallow=True):
                shutil.copy2(s, d)

    # === REMOVE STALE ===
    for root, dirs, files in os.walk(dst, topdown=False):
        rel = os.path.relpath(root, dst)
        source_root = src if rel == "." else os.path.join(src, rel)
        for name in files:
            if not os.path.exists(os.path.join(source_root, name)):
                os.remove(os.path.join(root, name))
        for name in dirs:
            if not os.path.exists(os.path.join(source_root, name)):
                shutil.rmtree(os.path.join(root, name), ignore_errors=True)


def link(src, dst):
    """Point dst at src with a symlink (Linux/macOS) or a junction (Windows, no admin needed).
    Refuses to replace a real, non-empty folder."""
    if not os.path.isdir(src):
        raise SyncError(f"Source missing: {src}")
    if is_link(dst):
        _unlink(dst)
    elif os.path.isdir(dst):
        if os.listdir(dst):
            raise SyncError(f"{dst} is a real folder. Remove it or switch this profile to Copy.")
        os.rmdir(dst)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if IS_WIN:
        import _winapi
        _winapi.CreateJunction(src, dst)
    else:
        os.symlink(src, dst, target_is_directory=True)


def sync_item(src, mod_dir, mod_id, mode):
    dst = os.path.join(mod_dir, mod_id)
    if mode == "link":
        link(src, dst)
    else:
        mirror_copy(src, dst)
    return dst
