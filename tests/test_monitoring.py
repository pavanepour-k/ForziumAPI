"""Tests for monitoring utilities."""

import importlib

import infrastructure.monitoring as mon


def test_exporter_choice_console(monkeypatch) -> None:
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "console")
    importlib.reload(mon)
    assert mon.get_exporter_choice() == "console"


def test_latency_histogram() -> None:
    mon.record_latency("/x", 10.0)
    mon.record_latency("/x", 20.0)
    assert list(mon.get_latency_histogram("/x")) == [10.0, 20.0]
