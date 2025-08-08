"""HTTP/2 utilities such as server push."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import List

_push_paths: ContextVar[List[str]] = ContextVar("_push_paths", default=[])


def _begin() -> Token[List[str]]:
    return _push_paths.set([])


def _end(token: Token[List[str]]) -> List[str]:
    paths = list(_push_paths.get())
    _push_paths.reset(token)
    return paths


def push(path: str) -> None:
    """Register *path* for HTTP/2 server push."""

    paths = list(_push_paths.get())
    paths.append(path)
    _push_paths.set(paths)


__all__ = ["push", "_begin", "_end"]
