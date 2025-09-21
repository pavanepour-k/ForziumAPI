"""Simple monitoring utilities with optional OpenTelemetry hooks."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from collections import defaultdict
from contextlib import nullcontext
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, Optional, Sequence
from urllib import request

from .otlp_exporter import OTLPBatchExporter

if TYPE_CHECKING:  # pragma: no cover
    from forzium.app import ForziumApp

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
_fail_dir = os.getenv("FORZIUM_OTLP_FAIL_DIR")
_metric_exporter: OTLPBatchExporter | None = None
_trace_exporter: OTLPBatchExporter | None = None
if _otlp_endpoint:
    _metric_exporter = OTLPBatchExporter(
        f"{_otlp_endpoint}/v1/metrics", fail_dir=_fail_dir
    )
    _trace_exporter = OTLPBatchExporter(
        f"{_otlp_endpoint}/v1/traces", fail_dir=_fail_dir
    )
_current_span: ContextVar[Optional[str]] = ContextVar("current_span", default=None)

_OBSERVABILITY_LOGGER = logging.getLogger("forzium.observability")


_telemetry_finalizers: list[Callable[[dict[str, Any]], None]] = []
_telemetry_finalizers_lock = threading.Lock()
_telemetry_finalizer_invocations = 0


def register_telemetry_finalizer(
    callback: Callable[[dict[str, Any]], None]
) -> Callable[[dict[str, Any]], None]:
    """Register *callback* to run when a request finishes."""

    with _telemetry_finalizers_lock:
        _telemetry_finalizers.append(callback)
    return callback


def unregister_telemetry_finalizer(
    callback: Callable[[dict[str, Any]], None]
) -> None:
    """Remove a previously registered telemetry finalizer."""

    with _telemetry_finalizers_lock:
        try:
            _telemetry_finalizers.remove(callback)
        except ValueError:
            pass


def reset_telemetry_finalizer_counters() -> None:
    """Reset invocation counters for telemetry finalizers."""

    global _telemetry_finalizer_invocations
    with _telemetry_finalizers_lock:
        _telemetry_finalizer_invocations = 0


def get_telemetry_finalizer_invocations() -> int:
    """Return the number of times telemetry finalizers have been run."""

    with _telemetry_finalizers_lock:
        return _telemetry_finalizer_invocations


def notify_telemetry_finalizers(payload: dict[str, Any]) -> None:
    """Invoke registered telemetry finalizers with *payload*."""

    callbacks: list[Callable[[dict[str, Any]], None]]
    with _telemetry_finalizers_lock:
        callbacks = list(_telemetry_finalizers)
    for callback in callbacks:
        try:
            callback(dict(payload))
        except Exception:  # pragma: no cover - finalizers must not raise
            _OBSERVABILITY_LOGGER.exception("telemetry finalizer raised")
    global _telemetry_finalizer_invocations
    with _telemetry_finalizers_lock:
        _telemetry_finalizer_invocations += 1


def _format_timestamp(value: float | None) -> str | None:
    if value is None:
        return None
    return (
        datetime.fromtimestamp(value, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


class _ObservabilityGate:
    """Coordinate when observability collection becomes active."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self._ready_timestamp: float | None = None
        self._metadata: dict[str, Any] = {}

    def is_ready(self) -> bool:
        """Return ``True`` once the gate has been opened."""

        return self._event.is_set()

    def mark_ready(
        self,
        *,
        source: str = "manual",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Open the gate and emit a structured log entry."""

        if not self._event.is_set():
            self._metadata = {"source": source, **(metadata or {})}
            self._ready_timestamp = time.time()
            self._event.set()
            _OBSERVABILITY_LOGGER.info(
                json.dumps(
                    {
                        "event": "obs-ready",
                        "status": "ready",
                        "source": source,
                        "metadata": self._metadata,
                        "timestamp": _format_timestamp(self._ready_timestamp),
                    },
                    separators=(",", ":"),
                )
            )
        return self.health()

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the gate is opened or *timeout* elapses."""

        return self._event.wait(timeout)

    def reset(self) -> None:
        """Return the gate to its initial state."""

        self._event.clear()
        self._ready_timestamp = None
        self._metadata = {}

    def health(self) -> dict[str, Any]:
        """Return readiness metadata for external consumers."""

        ready = self._event.is_set()
        payload: dict[str, Any] = {
            "ready": ready,
            "status": "ready" if ready else "initializing",
        }
        if self._ready_timestamp is not None:
            payload["since"] = _format_timestamp(self._ready_timestamp)
        if self._metadata:
            payload["metadata"] = dict(self._metadata)
        return payload


_observability_gate = _ObservabilityGate()


def mark_observability_ready(
    *, source: str = "manual", metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Mark observability collection as ready and return the health payload."""

    return _observability_gate.mark_ready(source=source, metadata=metadata)


def observability_ready() -> bool:
    """Return ``True`` if observability collection is active."""

    return _observability_gate.is_ready()


def wait_for_observability_ready(timeout: float | None = None) -> bool:
    """Wait for observability readiness up to *timeout* seconds."""

    return _observability_gate.wait(timeout)


def reset_observability_gate() -> None:
    """Reset the observability readiness state."""

    _observability_gate.reset()


def observability_health() -> dict[str, Any]:
    """Return a structured health payload describing readiness."""

    return _observability_gate.health()


@dataclass(slots=True)
class ManualSpan:
    """Fallback span implementation when OpenTelemetry is unavailable."""

    name: str
    span_id: str
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    attributes: dict[str, Any] = field(default_factory=dict)
    closed: bool = False
    exception_type: str | None = None

    def set_attribute(self, key: str, value: Any) -> None:
        """Record attribute *value* under *key*."""

        self.attributes[key] = value

    def get_span_context(self) -> SimpleNamespace:
        """Return a minimal span context exposing trace/span identifiers."""

        return SimpleNamespace(
            trace_id=int(self.trace_id, 16),
            span_id=int(self.span_id, 16),
        )

    def end(self, exc_type: type[BaseException] | None = None) -> None:
        """Mark the span as completed and capture optional exception type."""

        self.closed = True
        if exc_type is not None:
            self.exception_type = getattr(exc_type, "__name__", str(exc_type))


_manual_span_lookup: dict[str, ManualSpan] = {}
_manual_spans: list[ManualSpan] = []


def setup_tracing() -> bool:
    """Return whether OpenTelemetry tracing is active."""

    return _tracer_provider is not None


def tracing_enabled() -> bool:
    """Return ``True`` when an OpenTelemetry tracer is configured."""

    return _tracer_provider is not None and trace is not None


def current_trace_span() -> Any | None:
    """Return the active OpenTelemetry span when tracing is enabled."""

    if tracing_enabled():
        try:  # pragma: no cover - defensive in case tracing is partially configured
            return trace.get_current_span()  # type: ignore[return-value]
        except Exception:  # pragma: no cover - fallback when tracing backend missing
            return None
    span_id = _current_span.get()
    if span_id is None:
        return None
    return _manual_span_lookup.get(span_id)


def start_span(name: str):
    """Context manager yielding an active span if tracing is enabled."""

    span_id = uuid.uuid4().hex
    token = _current_span.set(span_id)
    manual_span: ManualSpan | None = None
    if _tracer_provider and trace is not None:
        tracer = trace.get_tracer("forzium")  # type: ignore[attr-defined]
        ctx = tracer.start_as_current_span(name)
    else:
        ctx = nullcontext()
        manual_span = ManualSpan(name=name, span_id=span_id)
        _manual_span_lookup[span_id] = manual_span

    class _SpanCtx:
        def __enter__(self):
            ctx.__enter__()
            return manual_span

        def __exit__(self, *exc):
            try:
                ctx.__exit__(*exc)
            finally:
                _current_span.reset(token)
                active = _manual_span_lookup.pop(span_id, None)
                if active is not None:
                    exc_type = exc[0] if exc else None
                    active.end(exc_type)
                    if not _span_exporter:
                        _manual_spans.append(active)

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
    if _trace_exporter:
        _trace_exporter.add({"spans": names})
        _trace_exporter.flush()
        return
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
        if _metric_exporter:
            _metric_exporter.add({"name": name, "value": value})
            _metric_exporter.flush()
            return
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


_alert_webhook = os.getenv("FORZIUM_ALERT_WEBHOOK")


def log_push_hints(hints: Sequence[Any], *, applied_at: float | None = None) -> None:
    """Emit a structured log entry describing HTTP/2 push hints."""

    if not hints:
        return

    applied_ts = applied_at or time.time()
    payload_hints: list[dict[str, Any]] = []
    for hint in hints:
        path = getattr(hint, "path", str(hint))
        registered_at = getattr(hint, "registered_at", None)
        registered_ts = registered_at if isinstance(registered_at, (int, float)) else None
        duration_ms = None
        if registered_ts is not None:
            duration_ms = max((applied_ts - registered_ts) * 1000.0, 0.0)
        payload_hints.append(
            {
                "path": path,
                "registered_at": _format_timestamp(registered_ts),
                "ms_until_apply": round(duration_ms, 3) if duration_ms is not None else None,
            }
        )

    _OBSERVABILITY_LOGGER.info(
        json.dumps(
            {
                "event": "http2.push",
                "count": len(payload_hints),
                "applied_at": _format_timestamp(applied_ts),
                "hints": payload_hints,
            },
            separators=(",", ":"),
        )
    )


def send_alert(message: str) -> None:
    """Send *message* to the configured alert webhook if set."""

    if not _alert_webhook:
        return
    body = json.dumps({"message": message}).encode()
    req = request.Request(
        _alert_webhook, data=body, headers={"Content-Type": "application/json"}
    )
    try:  # pragma: no cover - best effort
        with request.urlopen(req):
            pass
    except Exception:
        pass


def record_throughput(rps: float, baseline: float) -> None:
    """Record load-test *rps* and alert if below *baseline*."""

    record_metric("load_test_rps", rps)
    if rps < baseline:
        send_alert(
            f"load test throughput {rps:.2f} rps below baseline {baseline:.2f}"
        )


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


def flush_exporters() -> None:
    """Flush any configured OTLP exporters."""

    if _metric_exporter:
        _metric_exporter.flush()
    if _trace_exporter:
        _trace_exporter.flush()


def register_observability_persistence(app: "ForziumApp", db_path: str) -> None:
    """Persist metrics/traces to *db_path* when *app* shuts down."""

    def _shutdown() -> None:
        export_traces()
        flush_exporters()
        persist_observability(db_path)

    app.on_event("shutdown")(_shutdown)