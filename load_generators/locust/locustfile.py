"""Locust harness bound to the ForziumAPI scenario templates."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from gevent import sleep as gevent_sleep
from locust import HttpUser, LoadTestShape, between, events, task

from load_generators.common import ScenarioRuntime, load_runtime_from_file

LOGGER = logging.getLogger(__name__)
DEFAULT_SCENARIO_FILE = Path(__file__).resolve().parents[2] / "scenarios" / "release_v0_1_4.yaml"
DEFAULT_BASE_URL = os.getenv("FORZIUM_BASE_URL", "http://127.0.0.1:8000")

_RUNTIME: ScenarioRuntime | None = None
_STOP_REQUESTED = False


def _parse_optional_int(value: str | None) -> int | None:
    return int(value) if value not in {None, ""} else None


def _parse_optional_float(value: str | None) -> float | None:
    return float(value) if value not in {None, ""} else None


@events.init.add_listener
def _initialise(environment: Any, **_: Any) -> None:
    """Load the scenario runtime during Locust initialisation."""

    global _RUNTIME
    scenario_path = Path(os.getenv("FORZIUM_SCENARIO_FILE", str(DEFAULT_SCENARIO_FILE)))
    scenario_id = os.getenv("FORZIUM_SCENARIO_ID", "steady-baseline")
    duration_scale = float(os.getenv("FORZIUM_DURATION_SCALE", "1.0"))
    max_requests = _parse_optional_int(os.getenv("FORZIUM_MAX_REQUESTS"))
    ramp_resolution = _parse_optional_float(os.getenv("FORZIUM_RAMP_RESOLUTION"))
    LOGGER.info("Loading scenario id=%s from %s", scenario_id, scenario_path)
    _RUNTIME = load_runtime_from_file(
        scenario_path,
        scenario_id,
        duration_scale=duration_scale,
        max_requests=max_requests,
        ramp_resolution=ramp_resolution,
    )
    LOGGER.info(
        "Scenario %s ready: %d requests over %.1fs (concurrency=%d)",
        _RUNTIME.scenario.identifier,
        len(_RUNTIME.plan.entries),
        _RUNTIME.plan.total_duration_s,
        _RUNTIME.scenario.concurrency,
    )


@events.test_stop.add_listener
def _on_test_stop(environment: Any, **_: Any) -> None:
    runtime = _RUNTIME
    if runtime is None:
        return
    LOGGER.info(
        "Test stopped after executing %d of %d scheduled requests",
        len(runtime.plan.entries) - runtime.remaining,
        len(runtime.plan.entries),
    )


def _stop_runner(environment: Any) -> None:
    global _STOP_REQUESTED
    if _STOP_REQUESTED:
        return
    runner = getattr(environment, "runner", None)
    if runner is not None:
        LOGGER.info("Plan exhausted – signalling Locust runner shutdown")
        runner.quit()
    _STOP_REQUESTED = True


class ForziumUser(HttpUser):
    """Executes requests according to the deterministic scenario plan."""

    host = DEFAULT_BASE_URL
    wait_time = between(0, 0)

    @property
    def runtime(self) -> ScenarioRuntime | None:
        return _RUNTIME

    @events.test_start.add_listener  # type: ignore[misc]
    def _log_start(environment: Any, **_: Any) -> None:
        runtime = _RUNTIME
        if runtime is None:
            LOGGER.error("Scenario runtime not initialised – did init listener fail?")
        else:
            LOGGER.info(
                "Starting execution for %s (%d total requests)",
                runtime.scenario.identifier,
                len(runtime.plan.entries),
            )

    @events.test_stop.add_listener  # type: ignore[misc]
    def _log_stop(environment: Any, **_: Any) -> None:
        LOGGER.info("Locust test stop acknowledged")

    def on_start(self) -> None:
        if _RUNTIME is None:
            raise RuntimeError("Scenario runtime unavailable; ensure init listener executed")

    @task
    def execute_request(self) -> None:
        runtime = self.runtime
        if runtime is None:
            gevent_sleep(1.0)
            return
        entry = runtime.next_entry()
        if entry is None:
            _stop_runner(self.environment)
            gevent_sleep(1.0)
            return
        runtime.sleep_until(entry, gevent_sleep)
        resolved = runtime.resolve_request(entry)
        headers = dict(resolved.headers)
        name = f"{resolved.method} {resolved.stage}"
        with self.client.request(
            resolved.method,
            resolved.path,
            json=resolved.body,
            headers=headers,
            name=name,
            catch_response=True,
        ) as response:
            if not resolved.include_in_metrics:
                response.success()
                response._request_meta["name"] = f"warmup::{name}"

class ScenarioLoadShape(LoadTestShape):
    """Align Locust user count and spawn rate with scenario concurrency."""

    def tick(self) -> tuple[int, float] | None:
        runtime = _RUNTIME
        if runtime is None:
            return (1, 1)
        run_time = self.get_run_time()
        if runtime.completed and run_time > runtime.total_duration_s + 5.0:
            return None
        users = max(1, runtime.scenario.concurrency)
        spawn_rate = max(1.0, users / 2.0)
        return users, spawn_rate
