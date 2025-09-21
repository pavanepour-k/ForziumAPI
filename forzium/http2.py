"""HTTP/2 utilities such as server push."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Sequence
from contextvars import ContextVar, Token


@dataclass(slots=True)
class PushHint:
    """Information about a single server-push hint."""

    path: str
    registered_at: float


_push_paths: ContextVar[List[PushHint]] = ContextVar("_push_paths", default=[])


def _begin() -> Token[List[PushHint]]:
    return _push_paths.set([])


def _end(token: Token[List[PushHint]]) -> List[PushHint]:
    hints = list(_push_paths.get())
    _push_paths.reset(token)
    return hints


def push(path: str) -> None:
    """Register *path* for HTTP/2 server push."""

    hint_path = path.strip()
    if not hint_path:
        raise ValueError("push path must be a non-empty string")
    hints = list(_push_paths.get())
    hints.append(PushHint(path=hint_path, registered_at=time.time()))
    _push_paths.set(hints)


def format_link_header(hints: Sequence[PushHint]) -> str:
    """Return an RFC 5988 compatible ``Link`` header for *hints*."""

    return ", ".join(f"<{hint.path}>; rel=preload" for hint in hints)


__all__ = ["push", "_begin", "_end", "PushHint", "format_link_header"]