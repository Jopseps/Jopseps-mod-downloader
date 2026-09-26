# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
import importlib
import pkgutil

from jmd.handlers.base import GameHandler
from jmd.handlers.generic import GenericHandler

_registry = None


def _load():
    global _registry
    if _registry is None:
        _registry = {}
        for mod in pkgutil.iter_modules(__path__):
            if mod.name == "base":
                continue
            module = importlib.import_module(f"{__name__}.{mod.name}")
            for obj in vars(module).values():
                if isinstance(obj, type) and issubclass(obj, GameHandler) and obj is not GameHandler:
                    _registry[obj.key] = obj()
    return _registry


def for_app(app_id):
    for handler in _load().values():
        if int(app_id) in handler.app_ids:
            return handler
    return _load()["generic"]


def get(key):
    return _load().get(key) or _load()["generic"]
