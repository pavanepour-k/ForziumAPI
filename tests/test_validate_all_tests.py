"""Tests for the ``validate_all_tests`` utility."""

from pathlib import Path

from scripts import validate_all_tests as vat


def test_find_rust_roots_includes_engine() -> None:
    """Ensure the Rust engine crate is detected."""
    repo_root = Path(__file__).resolve().parent.parent
    crates = vat.find_rust_roots(repo_root)
    assert repo_root / "core" / "rust_engine" in crates  # nosec B101


def test_find_python_roots_includes_repo_root() -> None:
    """Ensure the repository root is treated as a Python module."""
    repo_root = Path(__file__).resolve().parent.parent
    modules = vat.find_python_roots(repo_root)
    assert repo_root in modules  # nosec B101
