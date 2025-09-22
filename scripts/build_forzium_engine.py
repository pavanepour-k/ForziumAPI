"""Stub builder used in test environments to satisfy extension imports."""

from __future__ import annotations

def build_forzium_engine() -> None:
    """Pretend to build the Rust extension when running in CI/tests."""

    return None