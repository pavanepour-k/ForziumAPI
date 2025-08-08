"""Lightweight file-based template renderer."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class TemplateRenderer:
    """Render templates stored on disk using ``str.format``."""

    def __init__(self, directory: str) -> None:
        self.directory = Path(directory)

    def render(self, template: str, **context: Any) -> str:
        """Return template *template* formatted with *context*."""
        text = (self.directory / template).read_text(encoding="utf8")
        return text.format(**context)


__all__ = ["TemplateRenderer"]
