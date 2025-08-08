"""Cancellation primitives for cooperative task termination."""

from __future__ import annotations


class CancellationToken:
    """Simple token to signal task cancellation across layers."""

    __slots__ = ("_cancelled",)

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        """Mark the token as cancelled."""
        self._cancelled = True

    def cancelled(self) -> bool:
        """Return whether cancellation was requested."""
        return self._cancelled


__all__ = ["CancellationToken"]
