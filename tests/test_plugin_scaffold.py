"""Verify CLI plugin scaffolding."""

from forzium.cli import main


def test_scaffold_plugin(tmp_path) -> None:
    main(["plugin", str(tmp_path), "demo"])
    assert (tmp_path / "pyproject.toml").exists()
    text = (tmp_path / "pyproject.toml").read_text()
    assert "forzium.plugins" in text
    pkg = tmp_path / "demo" / "__init__.py"
    assert pkg.exists()
