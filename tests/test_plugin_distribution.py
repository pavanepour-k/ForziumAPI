"""Validate packaging metadata for CLI plugins."""

import tomllib
from pathlib import Path


def test_sample_plugin_metadata() -> None:
    data = tomllib.loads(Path("plugins/sample_plugin/pyproject.toml").read_text())
    ep = data["project"]["entry-points"]["forzium.plugins"]
    assert ep["hello"] == "forzium_sample_plugin:register"


def test_scaffold_plugin_metadata() -> None:
    data = tomllib.loads(Path("plugins/pyproject.toml").read_text())
    ep = data["project"]["entry-points"]["forzium.plugins"]
    assert ep["scaffold"] == "forzium_plugin:register"
