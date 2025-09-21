"""Validate streaming response metrics against the committed baseline dataset."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from threading import Event
from typing import Iterable, Sequence


from forzium.app import ForziumApp
from forzium.http import BackgroundTasks
from forzium.responses import EventSourceResponse, StreamingResponse
from forzium.testclient import TestClient

STREAM_DELAYS: Sequence[float] = (0.05, 0.04, 0.06, 0.05)
EVENT_DELAYS: Sequence[float] = (0.03, 0.035, 0.025)
FAILURE_DELAYS: Sequence[float] = (0.04, 0.02)
DATASET_PATH = Path(__file__).resolve().parents[1] / "metrics" / "streaming_metrics_baseline.json"


class StreamingMetricsCollector:
    """Capture timing information for streamed chunks and background tasks."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.request_start: float | None = None
        self.chunk_timestamps: list[float] = []
        self.completed: bool = False
        self.error: Exception | None = None
        self.end_time: float | None = None
        self._background_start: float | None = None
        self._background_event = Event()

    def wrap_iterable(self, iterable: Iterable[bytes | dict[str, object]]) -> Iterable[bytes | dict[str, object]]:
        """Wrap *iterable* so that chunk timings are recorded lazily."""

        self.request_start = time.perf_counter()

        def iterator() -> Iterable[bytes | dict[str, object]]:
            try:
                for chunk in iterable:
                    now = time.perf_counter()
                    self.chunk_timestamps.append(now)
                    yield chunk
                self.completed = True
            except Exception as exc:  # pragma: no cover - defensive capture
                self.error = exc
                raise
            finally:
                self.end_time = time.perf_counter()

        return iterator()

    def mark_background_complete(self) -> None:
        """Mark the moment the background task begins executing."""

        self._background_start = time.perf_counter()
        self._background_event.set()

    def wait_for_background(self, timeout: float = 2.0) -> bool:
        """Wait until the background task starts (if any)."""

        return self._background_event.wait(timeout)

    def background_started_after_stream(self) -> bool:
        """Return ``True`` if background execution began post-stream."""

        return (
            self._background_start is not None
            and self.end_time is not None
            and self._background_start >= self.end_time
        )

    def to_metrics(self) -> dict[str, object]:
        """Convert captured timings into structured metrics."""

        if not self.chunk_timestamps:
            raise AssertionError("stream yielded no chunks")
        start = self.request_start or self.chunk_timestamps[0]
        ttfb_ms = round((self.chunk_timestamps[0] - start) * 1000.0, 3)
        intervals = [
            (b - a) * 1000.0 for a, b in zip(self.chunk_timestamps, self.chunk_timestamps[1:])
        ]
        if intervals:
            mean = sum(intervals) / len(intervals)
            variance = sum((val - mean) ** 2 for val in intervals) / len(intervals)
            stddev = math.sqrt(variance)
            cv = stddev / mean if mean else 0.0
        else:
            mean = 0.0
            stddev = 0.0
            cv = 0.0
        return {
            "label": self.label,
            "chunk_count": len(self.chunk_timestamps),
            "ttfb_ms": round(ttfb_ms, 3),
            "chunk_interval_mean_ms": round(mean, 3),
            "chunk_interval_stddev_ms": round(stddev, 3),
            "chunk_interval_cv": round(cv, 3),
            "background_executed": self._background_start is not None,
            "background_after_stream": self.background_started_after_stream(),
            "completed": self.completed,
        }


COLLECTORS: list[StreamingMetricsCollector] = []
app = ForziumApp()


def _register_collector(label: str) -> StreamingMetricsCollector:
    collector = StreamingMetricsCollector(label)
    COLLECTORS.append(collector)
    return collector


@app.get("/timed-stream")
def timed_stream(background: BackgroundTasks) -> StreamingResponse:
    collector = _register_collector("StreamingResponse")

    def generator() -> Iterable[bytes]:
        for idx, delay in enumerate(STREAM_DELAYS):
            time.sleep(delay)
            yield f"{{\"row\": {idx}}}\n".encode()

    background.add_task(collector.mark_background_complete)
    return StreamingResponse(
        collector.wrap_iterable(generator()),
        media_type="application/x-ndjson",
        background=background,
    )


@app.get("/timed-events")
def timed_events(background: BackgroundTasks) -> EventSourceResponse:
    collector = _register_collector("EventSourceResponse")

    def generator() -> Iterable[dict[str, object]]:
        for idx, delay in enumerate(EVENT_DELAYS):
            time.sleep(delay)
            yield {"event": "tick", "data": idx}

    background.add_task(collector.mark_background_complete)
    return EventSourceResponse(collector.wrap_iterable(generator()), background=background)


@app.get("/timed-stream-fail")
def timed_stream_fail() -> StreamingResponse:
    collector = _register_collector("StreamingResponseFailure")

    def generator() -> Iterable[bytes]:
        for idx, delay in enumerate(FAILURE_DELAYS):
            time.sleep(delay)
            if idx == 0:
                yield b"partial\n"
            else:
                raise RuntimeError("stream failure")

    return StreamingResponse(
        collector.wrap_iterable(generator()),
        media_type="application/x-ndjson",
    )


def _invoke(client: TestClient, method: str, path: str, expected_label: str):
    start = len(COLLECTORS)
    response = client.get(path) if method == "GET" else client.post(path)
    assert len(COLLECTORS) == start + 1
    collector = COLLECTORS[start]
    assert collector.label == expected_label
    return response, collector


def _assert_close(actual: float, expected: float, *, abs_tol: float, rel_tol: float) -> None:
    if expected == 0.0:
        assert abs(actual) <= abs_tol
    else:
        assert math.isclose(actual, expected, rel_tol=rel_tol, abs_tol=abs_tol)


def test_streaming_metrics_match_baseline() -> None:
    """Ensure measured streaming metrics align with the documented baseline."""

    COLLECTORS.clear()
    client = TestClient(app)
    results: list[dict[str, object]] = []

    resp_stream, collector_stream = _invoke(client, "GET", "/timed-stream", "StreamingResponse")
    assert resp_stream.status_code == 200
    assert resp_stream.chunks is not None
    assert collector_stream.wait_for_background()
    metrics_stream = collector_stream.to_metrics()
    assert metrics_stream["background_executed"]
    assert metrics_stream["background_after_stream"]
    assert len(resp_stream.chunks) == metrics_stream["chunk_count"]
    metrics_stream["status_code"] = resp_stream.status_code
    results.append(metrics_stream)

    resp_events, collector_events = _invoke(client, "GET", "/timed-events", "EventSourceResponse")
    assert resp_events.status_code == 200
    assert resp_events.chunks is not None
    assert collector_events.wait_for_background()
    metrics_events = collector_events.to_metrics()
    assert metrics_events["background_executed"]
    assert metrics_events["background_after_stream"]
    assert len(resp_events.chunks) == metrics_events["chunk_count"]
    metrics_events["status_code"] = resp_events.status_code
    results.append(metrics_events)

    resp_fail, collector_fail = _invoke(
        client, "GET", "/timed-stream-fail", "StreamingResponseFailure"
    )
    assert resp_fail.status_code == 500
    assert not collector_fail.wait_for_background(0.1)
    metrics_fail = collector_fail.to_metrics()
    assert not metrics_fail["background_executed"]
    assert not metrics_fail["background_after_stream"]
    metrics_fail["status_code"] = resp_fail.status_code
    results.append(metrics_fail)

    dataset = json.loads(DATASET_PATH.read_text())
    documented_runs = {entry["label"]: entry for entry in dataset["runs"]}

    for metrics in results:
        documented = documented_runs[metrics["label"]]
        for key in ("status_code", "chunk_count", "background_executed", "background_after_stream", "completed"):
            assert metrics[key] == documented[key]
        for key in ("ttfb_ms", "chunk_interval_mean_ms", "chunk_interval_stddev_ms"):
            _assert_close(metrics[key], documented[key], abs_tol=8.0, rel_tol=0.3)
        if metrics["chunk_interval_mean_ms"] == 0.0:
            assert documented["chunk_interval_cv"] == 0.0
        else:
            _assert_close(metrics["chunk_interval_cv"], documented["chunk_interval_cv"], abs_tol=0.1, rel_tol=0.3)

    total_runs = len(results)
    completed_runs = sum(1 for entry in results if entry["completed"])
    early_rate = (total_runs - completed_runs) / total_runs if total_runs else 0.0
    documented_aggregate = dataset["aggregate"]
    assert documented_aggregate["total_runs"] == total_runs
    assert documented_aggregate["completed_runs"] == completed_runs
    _assert_close(early_rate, documented_aggregate["early_termination_rate"], abs_tol=0.05, rel_tol=0.3)

    # Sanity: background tasks ran after stream completion for successful runs.
    assert collector_stream.background_started_after_stream()
    assert collector_events.background_started_after_stream()