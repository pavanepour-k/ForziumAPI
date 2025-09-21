"""Shared helpers for binding scenario templates to load generators."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Callable

from scripts.load_suite import (
    LoadScenarioDefinition,
    PlanEntry,
    ScenarioPlan,
    load_scenarios,
)

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ResolvedRequest:
    """Concrete HTTP request resolved from a scenario entry."""

    method: str
    path: str
    body: dict[str, Any] | None
    headers: dict[str, str]
    sequence: int
    stage: str
    include_in_metrics: bool
    offset_s: float


@dataclass(slots=True)
class ScenarioRuntime:
    """Thread-safe iterator over a scenario execution plan."""

    scenario: LoadScenarioDefinition
    plan: ScenarioPlan
    _index: int = field(default=0, init=False, repr=False)
    _start_time: float | None = field(default=None, init=False, repr=False)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _completed: bool = field(default=False, init=False, repr=False)

    def next_entry(self) -> PlanEntry | None:
        """Return the next plan entry, marking completion when exhausted."""

        with self._lock:
            if self._index >= len(self.plan.entries):
                self._completed = True
                return None
            entry = self.plan.entries[self._index]
            self._index += 1
            if self._start_time is None:
                self._start_time = time.perf_counter()
            return entry

    def sleep_until(self, entry: PlanEntry, sleeper: Callable[[float], None] | None = None) -> None:
        """Block until the schedule for ``entry`` should execute."""

        start = self._start_time
        if start is None:
            raise RuntimeError("Scenario runtime has not been initialised; call next_entry() first")
        sleep_fn = sleeper or time.sleep
        target = start + entry.offset_s
        while True:
            delay = target - time.perf_counter()
            if delay <= 0:
                break
            sleep_fn(min(delay, 0.5))

    def resolve_request(self, entry: PlanEntry) -> ResolvedRequest:
        """Materialise the HTTP request associated with ``entry``."""

        template = self.scenario.request
        path, _ = template.resolve_path(entry.sequence)
        payload = template.build_payload(entry.sequence)
        header, tenant = self.scenario.tenant_allocator.choose(entry.offset_s, entry.sequence)
        headers: dict[str, str] = {}
        if header:
            headers[header] = tenant
        if payload is not None:
            headers.setdefault("Content-Type", "application/json")
        return ResolvedRequest(
            method=template.method,
            path=path,
            body=payload,
            headers=headers,
            sequence=entry.sequence,
            stage=entry.stage,
            include_in_metrics=entry.include_in_metrics,
            offset_s=entry.offset_s,
        )

    @property
    def completed(self) -> bool:
        """Return whether the runtime has consumed all plan entries."""

        return self._completed

    @property
    def remaining(self) -> int:
        """Return the number of pending plan entries."""

        return max(len(self.plan.entries) - self._index, 0)

    @property
    def total_duration_s(self) -> float:
        """Return the total scheduled duration of the plan."""

        return self.plan.total_duration_s


def load_runtime_from_file(
    scenario_path: Path,
    scenario_id: str,
    *,
    duration_scale: float = 1.0,
    max_requests: int | None = None,
    ramp_resolution: float | None = None,
) -> ScenarioRuntime:
    """Load ``scenario_id`` from ``scenario_path`` and build a runtime plan."""

    definitions = load_scenarios(scenario_path, only=[scenario_id])
    if not definitions:
        raise ValueError(f"Scenario '{scenario_id}' not found in {scenario_path}")
    scenario = definitions[0]
    build_kwargs: dict[str, Any] = {
        "duration_scale": duration_scale,
        "max_requests": max_requests,
    }
    if ramp_resolution is not None:
        build_kwargs["ramp_resolution"] = ramp_resolution
    plan = scenario.build_plan(**build_kwargs)  # type: ignore[arg-type]
    LOGGER.info(
        "Loaded scenario %s from %s → %d plan entries (duration %.2fs)",
        scenario.identifier,
        scenario_path,
        len(plan.entries),
        plan.total_duration_s,
    )
    return ScenarioRuntime(scenario=scenario, plan=plan)


__all__ = [
    "ResolvedRequest",
    "ScenarioRuntime",
    "load_runtime_from_file",
]