# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
import errno
import filecmp
import os
import shutil
import sys

IS_WIN = sys.platform == "win32"


class SyncError(Exception):
    pass


class CrossDevice(SyncError):
    """Hardlinks can't span drives / filesystems."""


_WIN_NOT_SAME_DEVICE = 17


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
            if os.path.exists(d) and os.path.samefile(s, d):
                os.remove(d)  # left over from hardlink mode: copy2 would refuse, and edits would reach the cache
            if not os.path.exists(d) or not filecmp.cmp(s, d, shallow=True):
                shutil.copy2(s, d)

    _remove_stale(src, dst)


def _remove_stale(src, dst):
    """Delete what vanished upstream."""
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


def hardlink(src, dst):
    """Make dst a real folder whose files are hardlinks to src's: no extra space, and games that skip
    symlinked folders still load it. Raises CrossDevice when src and dst are on different filesystems."""
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
            if os.path.exists(d):
                if os.path.samefile(s, d):
                    continue
                os.remove(d)  # a copy, or an old link SteamCMD replaced in the cache
            try:
                os.link(s, d)
            except OSError as e:
                if e.errno == errno.EXDEV or getattr(e, "winerror", None) == _WIN_NOT_SAME_DEVICE:
                    raise CrossDevice(f"{src} and {dst} are on different drives") from e
                raise
    _remove_stale(src, dst)


def remove(path):
    """Take a synced mod out of the mod folder. A link goes without touching its target;
    a hardlinked folder only drops its links, the cache keeps the data."""
    if is_link(path):
        _unlink(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)


def sync_item(src, mod_dir, mod_id, mode, on_fallback=None):
    """Put one mod into mod_dir. Hardlink mode falls back to a copy across drives (on_fallback is told)."""
    dst = os.path.join(mod_dir, mod_id)
    if mode == "link":
        link(src, dst)
    elif mode == "hardlink":
        try:
            hardlink(src, dst)
        except CrossDevice as e:
            if on_fallback:
                on_fallback(str(e))
            mirror_copy(src, dst)
    else:
        mirror_copy(src, dst)
    return dst
