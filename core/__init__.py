"""Top-level package exposing Forzium components lazily."""

from importlib import import_module
from typing import Any

__all__ = ["app", "server"]


def __getattr__(name: str) -> Any:  # pragma: no cover - simple lazy importer
    if name == "app":
        module = import_module("core.app")
        return getattr(module, name)
    elif name == "server":
        module = import_module("core.server")
        return getattr(module, name)
    raise AttributeError(name)