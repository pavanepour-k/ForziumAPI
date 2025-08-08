"""Tests for CLI plugin discovery."""

from forzium.cli import main


def test_plugin_hello(capsys) -> None:
    main(["hello"])
    assert "hello plugin" in capsys.readouterr().out
