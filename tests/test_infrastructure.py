"""Tests for infrastructure utilities."""

import json

"""Infrastructure utilities covering config, deploy, and telemetry."""

import json

from infrastructure.configuration import load_settings
from infrastructure.deployment import build, run
from infrastructure.monitoring import (
    export_traces,
    get_current_span_id,
    get_metric,
    get_traces,
    health_check,
    record_metric,
    setup_tracing,
    start_span,
)
import forzium_engine


def test_load_settings_env(monkeypatch) -> None:
    """Environment variables override defaults."""
    monkeypatch.setenv("FORZIUM_ENV", "prod")
    monkeypatch.setenv("FORZIUM_DEBUG", "1")
    settings = load_settings()
    assert settings.environment == "prod"
    assert settings.debug is True


def test_deployment_commands() -> None:
    """Build and run return expected command lists."""
    assert build("img") == ["docker", "build", "-t", "img", "."]
    assert run("img") == ["docker", "run", "--rm", "img"]


def test_monitoring_metrics() -> None:
    """Metrics record, retrieve, and report health."""
    record_metric("requests", 5.0)
    assert get_metric("requests") == 5.0
    assert health_check() == {"status": "ok"}


def test_otlp_metric_export(monkeypatch) -> None:
    """Metrics send to OTLP endpoint when configured."""

    calls: list[tuple[str, bytes]] = []

    def fake_urlopen(req):
        calls.append((req.full_url, req.data))

        class Dummy:
            def __enter__(self):
                return self

            def __exit__(self, *exc) -> None:
                return None

            def read(self) -> bytes:
                return b""

        return Dummy()

    monkeypatch.setattr(
        "infrastructure.monitoring.request.urlopen",
        fake_urlopen,
    )
    monkeypatch.setattr(
        "infrastructure.monitoring._otlp_endpoint",
        "http://example",
    )
    record_metric("hit", 1.0)
    assert calls
    url, data = calls[0]
    assert url.endswith("/v1/metrics")
    payload = json.loads(data.decode())
    assert payload == {"name": "hit", "value": 1.0}


def test_tracing_span() -> None:
    """Tracing setup creates spans when available."""
    active = setup_tracing()
    with start_span("demo"):
        pass
    if active:
        traces = list(get_traces())
        assert any(span.name == "demo" for span in traces)


def test_span_correlation() -> None:
    """Rust bindings read the active Python span."""
    setup_tracing()
    with start_span("link"):
        py_id = get_current_span_id()
        rust_id = forzium_engine.current_span_id()
        assert rust_id == py_id


def test_otlp_trace_export(monkeypatch) -> None:
    """Finished spans send to OTLP endpoint."""

    calls: list[tuple[str, bytes]] = []

    def fake_urlopen(req):
        calls.append((req.full_url, req.data))

        class Dummy:
            def __enter__(self):
                return self

            def __exit__(self, *exc) -> None:
                return None

            def read(self) -> bytes:
                return b""

        return Dummy()

    monkeypatch.setattr("infrastructure.monitoring.request.urlopen", fake_urlopen)
    monkeypatch.setattr("infrastructure.monitoring._otlp_endpoint", "http://example")
    setup_tracing()
    with start_span("export"):
        pass
    export_traces()
    assert calls
    url, data = calls[0]
    assert url.endswith("/v1/traces")
