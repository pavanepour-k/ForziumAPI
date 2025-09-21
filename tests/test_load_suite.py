"""Tests for the load/stress/spike suite runner."""

from __future__ import annotations

from typing import Any

from scripts.load_suite import LoadScenarioDefinition, LoadSuiteRunner


def _scenario(
    identifier: str,
    pattern_type: str,
    pattern_payload: dict[str, Any],
    *,
    method: str = "GET",
    concurrency: int = 4,
    warmup: float = 0.0,
    seed_offset: int = 0,
) -> LoadScenarioDefinition:
    """Utility creating compact scenario definitions for tests."""

    seed_base = 10_000 + seed_offset * 100
    data = {
        "id": identifier,
        "name": identifier,
        "pattern": {"type": pattern_type, **pattern_payload},
        "concurrency": concurrency,
        "seed": {"traffic": seed_base, "payload": seed_base + 57},
        "request": {
            "method": method,
            "path": f"/suite/{identifier}/{{item_id}}",
            "payload_size_bytes": 128 if method != "GET" else 0,
            "payload_distribution": "lognormal" if method != "GET" else "fixed",
            "path_params": {
                "item_id": {
                    "distribution": "zipf",
                    "seed": seed_base + 11,
                    "parameters": {"s": 1.2, "size": 128},
                }
            },
        },
        "tenants": {
            "header": "X-Test-Tenant",
            "distribution": [
                {"tenant": "alpha", "weight": 0.6},
                {"tenant": "beta", "weight": 0.4},
            ],
        },
        "warmup": {"duration_s": warmup, "discard_metrics": True},
    }
    return LoadScenarioDefinition.from_dict(data)


def test_runner_executes_all_primary_patterns() -> None:
    scenarios = [
        _scenario("steady-mini", "steady", {"duration_s": 6, "target_rps": 18}, seed_offset=1),
        _scenario("poisson-mini", "poisson", {"duration_s": 6, "lambda_rps": 14}, seed_offset=2),
        _scenario(
            "burst-mini",
            "burst",
            {
                "stages": [
                    {"duration_s": 2, "target_rps": 10},
                    {"duration_s": 2, "target_rps": 25},
                    {"duration_s": 2, "target_rps": 12},
                ]
            },
            method="POST",
            seed_offset=3,
        ),
        _scenario(
            "ramp-mini",
            "ramp",
            {
                "phases": [
                    {"start_rps": 6, "end_rps": 16, "duration_s": 3},
                    {"start_rps": 16, "end_rps": 8, "duration_s": 3},
                ]
            },
            seed_offset=4,
        ),
    ]
    runner = LoadSuiteRunner(scenarios, service_time_ms=9.0, jitter_ms=0.5)
    report = runner.run(duration_scale=0.05, max_requests=120)
    observed = {entry["pattern"] for entry in report["scenarios"]}
    assert observed == {"steady", "poisson", "burst", "ramp"}
    for entry in report["scenarios"]:
        assert entry["total_requests"] > 0
        assert entry["included_requests"] > 0
        assert entry["metrics"]["latency_ms"]["mean"] > 0.0
        assert entry["stage_metrics"], "expected per-stage metrics"


def test_runner_reports_failure_modes_and_saturation() -> None:
    saturated = _scenario(
        "steady-saturated",
        "steady",
        {"duration_s": 8, "target_rps": 60},
        concurrency=2,
        seed_offset=10,
    )
    runner = LoadSuiteRunner(
        [saturated],
        service_time_ms=55.0,
        jitter_ms=0.0,
        error_profile={"steady-saturated": {"steady": 1.0}},
    )
    report = runner.run(duration_scale=0.05, max_requests=200)
    scenario_report = report["scenarios"][0]
    assert scenario_report["failure_modes"], "expected injected failure modes"
    assert any(
        point["stage"] == "steady" for point in scenario_report["saturation_points"]
    ), "steady stage should saturate under high demand"