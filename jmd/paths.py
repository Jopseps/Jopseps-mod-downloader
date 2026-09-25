import os
import sys

from jmd import APP_SLUG


def data_dir():
    """Per-user app data folder: ~/.local/share/jmod on Linux, %LOCALAPPDATA%\\jmod on Windows."""
    override = os.environ.get("JMD_DATA_DIR")
    if override:
        return override
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, APP_SLUG)


def ensure(path):
    os.makedirs(path, exist_ok=True)
    return path


def steamcmd_dir():
    """Where an auto-bootstrapped SteamCMD lives."""
    return os.path.join(data_dir(), "steamcmd")


def cache_dir():
    """App-owned SteamCMD force_install_dir (workshop cache = source of truth)."""
    return os.path.join(data_dir(), "cache")


def thumbs_dir():
    return os.path.join(data_dir(), "thumbs")


def profiles_dir():
    return os.path.join(data_dir(), "profiles")


def asset(*parts):
    """Path to a bundled asset (works from source and from PyInstaller)."""
    root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    if hasattr(sys, "_MEIPASS"):
        root = os.path.join(root, "jmd")
    return os.path.join(root, "assets", *parts)
