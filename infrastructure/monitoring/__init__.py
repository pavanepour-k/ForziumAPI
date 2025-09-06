"""Simple monitoring utilities with optional OpenTelemetry hooks."""

import json
import os
import sqlite3
import uuid
from collections import defaultdict
from contextlib import nullcontext
from contextvars import ContextVar
from typing import Dict, Iterable, Optional
from urllib import request

_exporter_choice = os.getenv("OTEL_TRACES_EXPORTER", "inmemory")

try:  # pragma: no cover - optional dependency
    from opentelemetry import metrics, trace  # type: ignore
    from opentelemetry.sdk.metrics import MeterProvider  # type: ignore
    from opentelemetry.sdk.trace import TracerProvider  # type: ignore
    from opentelemetry.sdk.trace.export import (  # type: ignore
        ConsoleSpanExporter,
        InMemorySpanExporter,
        SimpleSpanProcessor,
    )

    if _exporter_choice == "console":
        _span_exporter = ConsoleSpanExporter()
    else:
        _span_exporter = InMemorySpanExporter()
    _tracer_provider = TracerProvider()
    _tracer_provider.add_span_processor(SimpleSpanProcessor(_span_exporter))
    trace.set_tracer_provider(_tracer_provider)
    _meter_provider = MeterProvider()
    metrics.set_meter_provider(_meter_provider)
except Exception:  # pragma: no cover - telemetry disabled
    trace = metrics = None  # type: ignore
    _span_exporter = None
    _tracer_provider = None
    _meter_provider = None

_metrics: Dict[str, float] = {}
_latency_histograms: Dict[str, list[float]] = defaultdict(list)
_otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
_current_span: ContextVar[Optional[str]] = ContextVar("current_span", default=None)
_manual_spans: list[str] = []


def setup_tracing() -> bool:
    """Return whether OpenTelemetry tracing is active."""

    return _tracer_provider is not None


def start_span(name: str):
    """Context manager yielding an active span if tracing is enabled."""

    span_id = str(uuid.uuid4())
    token = _current_span.set(span_id)
    if _tracer_provider:
        tracer = trace.get_tracer("forzium")  # type: ignore[attr-defined]
        ctx = tracer.start_as_current_span(name)
    else:
        ctx = nullcontext()

    class _SpanCtx:
        def __enter__(self):
            ctx.__enter__()
            return None

        def __exit__(self, *exc):
            ctx.__exit__(*exc)
            _current_span.reset(token)
            if not _span_exporter:
                _manual_spans.append(name)

    return _SpanCtx()


def get_traces() -> Iterable[object]:
    """Retrieve finished spans when tracing is active."""

    if _span_exporter:
        return _span_exporter.get_finished_spans()
    return list(_manual_spans)


def export_traces() -> None:
    """Send collected spans to the OTLP endpoint if configured."""

    if not _otlp_endpoint:
        return
    names = [getattr(span, "name", "") for span in get_traces()]
    body = json.dumps(names).encode()
    req = request.Request(
        f"{_otlp_endpoint}/v1/traces",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:  # pragma: no cover - best effort
        with request.urlopen(req):
            pass
    except Exception:
        pass


def record_metric(name: str, value: float) -> None:
    """Store a metric and optionally send it via OTLP."""

    if _meter_provider:
        meter = metrics.get_meter("forzium")  # type: ignore[attr-defined]
        counter = meter.create_counter(name)
        counter.add(value)
    _metrics[name] = value
    if _otlp_endpoint:
        body = json.dumps({"name": name, "value": value}).encode()
        req = request.Request(
            f"{_otlp_endpoint}/v1/metrics",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:  # pragma: no cover - best effort
            with request.urlopen(req):
                pass
        except Exception:
            pass


def get_metric(name: str) -> float:
    """Retrieve a recorded metric."""

    return _metrics.get(name, 0.0)


def record_latency(endpoint: str, duration_ms: float) -> None:
    """Record latency for *endpoint* in milliseconds."""

    _latency_histograms[endpoint].append(duration_ms)


def get_latency_histogram(endpoint: str) -> Iterable[float]:
    """Return recorded latencies for *endpoint*."""

    return _latency_histograms.get(endpoint, [])


def prometheus_metrics() -> str:
    """Render recorded metrics in Prometheus text format."""

    return "\n".join(f"{k} {v}" for k, v in _metrics.items())


def get_exporter_choice() -> str:
    """Expose which tracing exporter is active."""

    return _exporter_choice


def get_current_span_id() -> Optional[str]:
    """Return identifier for the active span if any."""

    return _current_span.get()


def health_check() -> dict[str, str]:
    """Return service liveness information."""

    return {"status": "ok"}


def persist_observability(db_path: str) -> None:
    """Persist latency histograms and traces to *db_path*."""

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS latencies (endpoint TEXT, duration REAL)")
    cur.execute("CREATE TABLE IF NOT EXISTS traces (name TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS metrics (name TEXT, value REAL)")
    for endpoint, values in _latency_histograms.items():
        cur.executemany(
            "INSERT INTO latencies VALUES (?, ?)",
            [(endpoint, v) for v in values],
        )
    for name, value in _metrics.items():
        cur.execute("INSERT INTO metrics VALUES (?, ?)", (name, value))
    for span in get_traces():
        name = span if isinstance(span, str) else getattr(span, "name", "")
        cur.execute("INSERT INTO traces VALUES (?)", (name,))
    conn.commit()
    conn.close()


def query_metric(db_path: str, name: str) -> float | None:
    """Fetch *name* from persisted metrics in *db_path*."""

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT value FROM metrics WHERE name=?", (name,))
    row = cur.fetchone()
    conn.close()
    return float(row[0]) if row else None
