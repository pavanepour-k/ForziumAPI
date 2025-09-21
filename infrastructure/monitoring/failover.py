"""Analyze failover and chaos engineering runs for stability regressions."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import json

ISO_Z_SUFFIX = "Z"


def _parse_timestamp(value: str) -> datetime:
    """Parse ISO 8601 timestamps accepting ``Z`` suffixes."""

    value = value.strip()
    if value.endswith(ISO_Z_SUFFIX):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(timezone.utc)


@dataclass(slots=True)
class ChaosEvent:
    """A single event captured during the chaos experiment."""

    timestamp: datetime
    component: str
    kind: str
    metadata: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ChaosEvent":
        required = {"timestamp", "component", "kind"}
        missing = required.difference(payload)
        if missing:
            raise ValueError(f"event missing keys: {sorted(missing)}")
        timestamp = _parse_timestamp(str(payload["timestamp"]))
        component = str(payload["component"])
        kind = str(payload["kind"]).lower()
        metadata = dict(payload.get("metadata", {}))
        return cls(timestamp=timestamp, component=component, kind=kind, metadata=metadata)


@dataclass(slots=True)
class ResourceSnapshot:
    """A before/after pair for a tracked resource counter."""

    name: str
    baseline: int
    post_recovery: int
    max_delta: int | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ResourceSnapshot":
        required = {"name", "baseline", "post_recovery"}
        missing = required.difference(payload)
        if missing:
            raise ValueError(f"resource snapshot missing keys: {sorted(missing)}")
        return cls(
            name=str(payload["name"]),
            baseline=int(payload["baseline"]),
            post_recovery=int(payload["post_recovery"]),
            max_delta=(int(payload["max_delta"]) if "max_delta" in payload else None),
        )

    @property
    def delta(self) -> int:
        """Return the post-recovery delta relative to the baseline."""

        return self.post_recovery - self.baseline


@dataclass(slots=True)
class FailoverConfig:
    """Thresholds applied while evaluating chaos experiments."""

    max_recovery_seconds: float
    stability_window_seconds: float
    resource_tolerances: dict[str, int]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FailoverConfig":
        required = {"max_recovery_seconds", "stability_window_seconds", "resource_tolerances"}
        missing = required.difference(payload)
        if missing:
            raise ValueError(f"config missing keys: {sorted(missing)}")
        tolerances = payload.get("resource_tolerances")
        if not isinstance(tolerances, dict):
            raise ValueError("resource_tolerances must be a mapping")
        return cls(
            max_recovery_seconds=float(payload["max_recovery_seconds"]),
            stability_window_seconds=float(payload["stability_window_seconds"]),
            resource_tolerances={str(key): int(value) for key, value in tolerances.items()},
        )


@dataclass(slots=True)
class FailoverRun:
    """Aggregated data for a chaos engineering run."""

    metadata: dict[str, Any]
    events: list[ChaosEvent]
    resources: list[ResourceSnapshot]

    def __post_init__(self) -> None:
        if not self.events:
            raise ValueError("failover run requires at least one event")
        self.events.sort(key=lambda event: event.timestamp)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FailoverRun":
        metadata = dict(payload.get("metadata", {}))
        raw_events = payload.get("events")
        if not isinstance(raw_events, Sequence) or not raw_events:
            raise ValueError("failover run requires at least one event")
        events = [ChaosEvent.from_dict(dict(item)) for item in raw_events]
        raw_resources = payload.get("resources", [])
        if not isinstance(raw_resources, Iterable):
            raise ValueError("resources must be iterable")
        resources = [ResourceSnapshot.from_dict(dict(item)) for item in raw_resources]
        return cls(metadata=metadata, events=events, resources=resources)


@dataclass(slots=True)
class ComponentRecovery:
    """Outcome for a single component during the chaos run."""

    component: str
    failure_at: datetime
    failure_metadata: dict[str, Any]
    recovery_at: datetime | None
    recovery_metadata: dict[str, Any] | None

    @property
    def recovered(self) -> bool:
        return self.recovery_at is not None

    @property
    def recovery_seconds(self) -> float | None:
        if not self.recovery_at:
            return None
        delta = self.recovery_at - self.failure_at
        return delta.total_seconds()


@dataclass(slots=True)
class FailoverReport:
    """Structured evaluation result for a chaos experiment."""

    passed: bool
    recovered: bool
    max_recovery_seconds: float
    leak_count: int
    stability_confirmed: bool
    component_results: list[ComponentRecovery]
    violations: list[str]

    def to_gate_payload(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "recovered": self.recovered,
            "max_recovery_seconds": round(self.max_recovery_seconds, 3),
            "leak_count": self.leak_count,
            "stability_confirmed": self.stability_confirmed,
            "violations": self.violations,
        }


class FailoverAnalyzer:
    """Evaluate chaos experiments using ``FailoverConfig`` thresholds."""

    def __init__(self, config: FailoverConfig) -> None:
        self._config = config

    def evaluate(self, run: FailoverRun) -> FailoverReport:
        pending_failures: dict[str, deque[tuple[datetime, dict[str, Any]]]] = defaultdict(deque)
        component_results: list[ComponentRecovery] = []
        latest_recovery: datetime | None = None

        # Track stability events for post-recovery validation.
        stability_events: list[ChaosEvent] = []

        for event in run.events:
            if event.kind == "failure":
                pending_failures[event.component].append((event.timestamp, event.metadata))
            elif event.kind == "recovery":
                queue = pending_failures[event.component]
                if queue:
                    failure_at, failure_meta = queue.popleft()
                    result = ComponentRecovery(
                        component=event.component,
                        failure_at=failure_at,
                        failure_metadata=failure_meta,
                        recovery_at=event.timestamp,
                        recovery_metadata=event.metadata,
                    )
                    component_results.append(result)
                    if latest_recovery is None or event.timestamp > latest_recovery:
                        latest_recovery = event.timestamp
                else:
                    # Recovery without a recorded failure – treat as instantaneous.
                    result = ComponentRecovery(
                        component=event.component,
                        failure_at=event.timestamp,
                        failure_metadata={},
                        recovery_at=event.timestamp,
                        recovery_metadata=event.metadata,
                    )
                    component_results.append(result)
                    if latest_recovery is None or event.timestamp > latest_recovery:
                        latest_recovery = event.timestamp
            elif event.kind == "stability":
                stability_events.append(event)

        # Any remaining failures did not recover.
        for component, queue in pending_failures.items():
            while queue:
                failure_at, failure_meta = queue.popleft()
                component_results.append(
                    ComponentRecovery(
                        component=component,
                        failure_at=failure_at,
                        failure_metadata=failure_meta,
                        recovery_at=None,
                        recovery_metadata=None,
                    )
                )

        recovered = all(result.recovered for result in component_results)
        max_recovery_seconds = max(
            (result.recovery_seconds or 0.0) for result in component_results
        ) if component_results else 0.0

        violations: list[str] = []
        if not recovered:
            violations.append("one or more components failed to recover")
        if max_recovery_seconds > self._config.max_recovery_seconds:
            violations.append(
                "max recovery time exceeded: "
                f"{max_recovery_seconds:.3f}s > {self._config.max_recovery_seconds:.3f}s"
            )

        leak_count = 0
        for resource in run.resources:
            tolerance = self._config.resource_tolerances.get(resource.name, 0)
            if resource.max_delta is not None:
                tolerance = min(tolerance, resource.max_delta) if resource.name in self._config.resource_tolerances else resource.max_delta
            if resource.delta > tolerance:
                leak_count += 1
                violations.append(
                    (
                        f"resource {resource.name} leaked {resource.delta} "
                        f"(budget {tolerance})"
                    )
                )

        last_recovery = latest_recovery
        stability_confirmed = False
        if component_results:
            if last_recovery is not None:
                for event in stability_events:
                    if event.timestamp < last_recovery:
                        continue
                    window = float(event.metadata.get("window_seconds", 0.0))
                    elapsed = (event.timestamp - last_recovery).total_seconds()
                    if (
                        window >= self._config.stability_window_seconds
                        or elapsed >= self._config.stability_window_seconds
                    ):
                        stability_confirmed = True
                        break
            else:
                stability_confirmed = False
        else:
            # If no failures were injected, consider stability trivially confirmed.
            stability_confirmed = True

        if component_results and not stability_confirmed:
            violations.append("stability window not confirmed after recovery")

        passed = (
            recovered
            and leak_count == 0
            and max_recovery_seconds <= self._config.max_recovery_seconds
            and stability_confirmed
        )

        return FailoverReport(
            passed=passed,
            recovered=recovered,
            max_recovery_seconds=max_recovery_seconds,
            leak_count=leak_count,
            stability_confirmed=stability_confirmed,
            component_results=component_results,
            violations=violations,
        )


def load_failover_run(path: Path) -> tuple[FailoverRun, FailoverConfig]:
    """Load a ``FailoverRun`` and ``FailoverConfig`` from *path*."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    run = FailoverRun.from_dict(payload)
    config_payload = payload.get("config")
    if not isinstance(config_payload, dict):
        raise ValueError("config section missing from failover payload")
    config = FailoverConfig.from_dict(config_payload)
    return run, config


def evaluate_failover_file(path: Path) -> FailoverReport:
    """Convenience helper mirroring ``evaluate_soak_file`` semantics."""

    run, config = load_failover_run(path)
    return FailoverAnalyzer(config).evaluate(run)