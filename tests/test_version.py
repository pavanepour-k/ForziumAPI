"""Regression tests for public version exposure."""

from __future__ import annotations

import importlib
import pathlib
import re
from typing import Iterable

import tomllib


def _project_root() -> pathlib.Path:
    """Return the repository root for fixture location."""

    return pathlib.Path(__file__).resolve().parents[1]


def _load_forzium_module():
    """Import the top-level package lazily for reuse within tests."""

    return importlib.import_module("forzium")


def _assert_text_contains(path: pathlib.Path, pattern: str) -> None:
    """Assert a regex pattern is present inside a UTF-8 encoded text file."""

    text = path.read_text(encoding="utf-8")
    assert re.search(pattern, text), f"Expected to find pattern {pattern!r} in {path}"


def _toml_lookup(data: dict[str, object], keys: Iterable[str]) -> object:
    """Traverse a TOML document using a sequence of keys."""

    current: object = data
    for key in keys:
        assert isinstance(current, dict), f"Intermediate value for {keys} is not a table"
        current = current[key]
    return current


def test_forzium_version_constant() -> None:
    """Ensure the version constant is exposed and matches the release tag."""

    module = _load_forzium_module()
    assert module.__version__ == "0.1.4"


def test_forzium_version_constant_is_string() -> None:
    """The exported version must remain a simple immutable string."""

    module = _load_forzium_module()
    assert isinstance(module.__version__, str)


def test_version_consistency_across_artifacts() -> None:
    """Cross-validate the release version across build metadata and scaffolding."""

    module = _load_forzium_module()
    version = module.__version__
    root = _project_root()

    toml_targets: dict[pathlib.Path, tuple[tuple[str, ...], ...]] = {
        root / "pyproject.toml": (
            ("project", "version"),
            ("tool", "poetry", "version"),
        ),
        root / "core" / "rust_engine" / "Cargo.toml": (
            ("package", "version"),
        ),
        root / "plugins" / "pyproject.toml": (
            ("project", "version"),
        ),
        root / "plugins" / "sample_plugin" / "pyproject.toml": (
            ("project", "version"),
        ),
    }

    for path, lookups in toml_targets.items():
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        for keys in lookups:
            assert (
                _toml_lookup(data, keys) == version
            ), f"{path}::{"/".join(keys)} expected {version}"

    escaped_version = re.escape(version)
    textual_patterns: dict[pathlib.Path, tuple[str, ...]] = {
        root / "README.md": (rf"v{escaped_version}",),
        root / "docs" / "migration.md": (rf"v{escaped_version}",),
        root / "docs" / "scenario_templates.md": (rf"v{escaped_version}",),
        root / "Test_Strategy.md": (rf"v{escaped_version}",),
        root
        / "forzium"
        / "cli.py": (
            rf"forzium=={escaped_version}\\nforzium-engine=={escaped_version}\\n",
            rf"version = \"{escaped_version}\"\\n",
        ),
        root
        / "infrastructure"
        / "deployment"
        / "templates"
        / "docker-compose.yml": (rf":{escaped_version}\b",),
        root
        / "infrastructure"
        / "deployment"
        / "templates"
        / "kubernetes"
        / "staging-job.yaml": (rf":{escaped_version}\b",),
        root
        / "infrastructure"
        / "deployment"
        / "templates"
        / "helm"
        / "Chart.yaml": (rf"\"{escaped_version}\"",),
        root
        / "infrastructure"
        / "monitoring"
        / "dashboards"
        / "forzium_observability.json": (rf"\"forzium_release\": \"{escaped_version}\"",),
        root / "scenarios" / "release_v0_1_4.yaml": (rf"v{escaped_version}",),
        root / "scenarios" / "release_v0_1_4.json": (rf"v{escaped_version}",),
    }

    for path, patterns in textual_patterns.items():
        for pattern in patterns:
            _assert_text_contains(path, pattern)