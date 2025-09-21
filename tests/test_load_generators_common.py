"""Tests for the shared load generator runtime helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

from load_generators.common import ResolvedRequest, load_runtime_from_file


@pytest.fixture
def scenario_file(tmp_path: Path) -> Path:
    """Persist a compact scenario definition for runtime tests."""

    scenario = {
        "id": "steady-mini",
        "pattern": {"type": "steady", "duration_s": 1.0, "target_rps": 2.0},
        "concurrency": 2,
        "warmup": {"duration_s": 1.0, "discard_metrics": True},
        "request": {
            "method": "POST",
            "path": "/items/{item_id}",
            "payload_size_bytes": 16,
            "payload_distribution": "fixed",
            "path_params": {
                "item_id": {
                    "distribution": "sequential",
                    "parameters": {"start": 10},
                }
            },
        },
        "tenants": {
            "header": "X-Tenant-ID",
            "rotation_order": {
                "sequence": ["tenant-a", "tenant-b"],
                "cycle_seconds": 1.0,
            },
        },
        "seed": {"traffic": 101, "payload": 202},
    }
    data = {"scenarios": [scenario]}
    path = tmp_path / "scenario.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _perf_counter(values: list[float]) -> Callable[[], float]:
    """Return a perf_counter stub that steps through ``values`` then repeats."""

    last = values[-1]
    index = 0

    def _inner() -> float:
        nonlocal index, last
        if index < len(values):
            last = values[index]
            index += 1
            return last
        return last

    return _inner


def test_runtime_iteration_and_resolution(
    scenario_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_runtime_from_file(scenario_file, "steady-mini", duration_scale=1.0)
    # Warm-up stage should be first and excluded from metrics.
    monkeypatch.setattr(
        "load_generators.common.time.perf_counter",
        _perf_counter([100.0, 100.0, 100.5, 101.0]),
    )
    consumed = 0
    first = runtime.next_entry()
    assert first is not None
    assert first.stage == "warmup"
    assert first.include_in_metrics is False
    consumed += 1

    primary = runtime.next_entry()
    while primary is not None and primary.stage == "warmup":
        consumed += 1
        primary = runtime.next_entry()
    assert primary is not None, "expected a primary stage entry after warmup"
    assert primary.stage != "warmup"
    consumed += 1

    sleeps: list[float] = []
    runtime.sleep_until(primary, sleeps.append)
    assert sum(sleeps) == pytest.approx(primary.offset_s, rel=1e-6)

    resolved = runtime.resolve_request(primary)
    assert isinstance(resolved, ResolvedRequest)
    assert resolved.method == "POST"
    assert resolved.path.startswith("/items/")
    assert resolved.sequence == primary.sequence
    assert resolved.headers["X-Tenant-ID"] in {"tenant-a", "tenant-b"}
    assert resolved.headers["Content-Type"] == "application/json"
    assert resolved.body is not None
    assert resolved.body["sequence"] == primary.sequence
    assert len(resolved.body["blob"]) == 16
    assert runtime.remaining == len(runtime.plan.entries) - consumed
    assert runtime.completed is False


def test_runtime_honours_max_requests(scenario_file: Path) -> None:
    runtime = load_runtime_from_file(
        scenario_file,
        "steady-mini",
        duration_scale=1.0,
        max_requests=3,
    )
    sequences: list[int] = []
    while (entry := runtime.next_entry()) is not None:
        sequences.append(entry.sequence)
    assert len(sequences) == 3
    assert sequences == sorted(sequences)
    assert runtime.completed is True
    assert runtime.remaining == 0


def test_missing_scenario_raises(tmp_path: Path) -> None:
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"scenarios": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_runtime_from_file(empty, "does-not-exist")