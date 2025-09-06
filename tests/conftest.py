"""Pytest configuration for Forzium tests.

Ensures the Rust `forzium_engine` extension is built before any tests
execute. This allows the suite to run in fresh environments without the
wheel pre-installed.
"""

from __future__ import annotations

import pathlib
import sys

# Make the `scripts` directory importable so we can reuse the build helper.
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))
from build_forzium_engine import build_forzium_engine  # noqa: E402


def pytest_sessionstart(session) -> None:
    """Build the Rust extension if it's missing."""
    build_forzium_engine()
