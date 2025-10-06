"""Soak test evaluation primitives.

This module loads long-running stability samples collected during nightly soak
runs and evaluates them against gating thresholds.  The implementation focuses
on deterministic parsing and reproducible scoring so that release automation can
assert the acceptance criteria:

* No container restarts occurred during the soak.
* Span closure ratio must be 100% (every started span closed).
* Memory (RSS) drift stays within the configured budget.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import json

ISO_Z_SUFFIX = "Z"


def _parse_timestamp(value: str) -> datetime:
    """Parse ISO 8601 timestamps with optional ``Z`` suffix."""

    if value.endswith(ISO_Z_SUFFIX):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(timezone.utc)


@dataclass(slots=True)
class SoakSample:
    """Single time series point captured during the soak."""

    timestamp: datetime
    rss_bytes: int
    container_restarts: int
    spans_started: int
    spans_closed: int

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SoakSample":
        required = {"timestamp", "rss_bytes", "container_restarts", "spans_started", "spans_closed"}
        missing = required.difference(payload)
        if missing:
            raise ValueError(f"sample missing keys: {sorted(missing)}")
        timestamp = _parse_timestamp(str(payload["timestamp"]))
        return cls(
            timestamp=timestamp,
            rss_bytes=int(payload["rss_bytes"]),
            container_restarts=int(payload["container_restarts"]),
            spans_started=int(payload["spans_started"]),
            spans_closed=int(payload["spans_closed"]),
        )


@dataclass(slots=True)
class SoakConfig:
    """Thresholds applied when evaluating soak runs."""

    min_duration_hours: float
    rss_drift_budget_bytes: int
    max_container_restarts: int

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SoakConfig":
        required = {"min_duration_hours", "rss_drift_budget_bytes", "max_container_restarts"}
        missing = required.difference(payload)
        if missing:
            raise ValueError(f"config missing keys: {sorted(missing)}")
        return cls(
            min_duration_hours=float(payload["min_duration_hours"]),
            rss_drift_budget_bytes=int(payload["rss_drift_budget_bytes"]),
            max_container_restarts=int(payload["max_container_restarts"]),
        )


@dataclass(slots=True)
class SoakRun:
    """Container aggregating the full soak time series."""

    metadata: dict[str, Any]
    samples: list[SoakSample]

    def __post_init__(self) -> None:
        if len(self.samples) < 2:
            raise ValueError("soak run requires at least two samples")
        self.samples.sort(key=lambda sample: sample.timestamp)
        self._validate_monotonicity(self.samples)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SoakRun":
        metadata = dict(payload.get("metadata", {}))
        raw_samples = payload.get("samples")
        if not isinstance(raw_samples, Sequence) or len(raw_samples) < 2:
            raise ValueError("soak run requires at least two samples")
        samples = [SoakSample.from_dict(dict(item)) for item in raw_samples]
        return cls(metadata=metadata, samples=samples)

    @staticmethod
    def _validate_monotonicity(samples: Sequence[SoakSample]) -> None:
        """Ensure cumulative counters never regress."""

        for prev, current in zip(samples, samples[1:]):
            if current.timestamp <= prev.timestamp:
                raise ValueError("timestamps must be strictly increasing")
            if current.container_restarts < prev.container_restarts:
                raise ValueError("container restart counter regressed")
            if current.spans_started < prev.spans_started:
                raise ValueError("span start counter regressed")
            if current.spans_closed < prev.spans_closed:
                raise ValueError("span close counter regressed")

    @property
    def duration_hours(self) -> float:
        delta = self.samples[-1].timestamp - self.samples[0].timestamp
        return delta.total_seconds() / 3600.0

    @property
    def container_restart_delta(self) -> int:
        return self.samples[-1].container_restarts - self.samples[0].container_restarts

    @property
    def rss_min(self) -> int:
        return min(sample.rss_bytes for sample in self.samples)

    @property
    def rss_max(self) -> int:
        return max(sample.rss_bytes for sample in self.samples)

    @property
    def rss_drift(self) -> int:
        return self.rss_max - self.rss_min

    def span_totals(self) -> tuple[int, int]:
        started = self.samples[-1].spans_started - self.samples[0].spans_started
        closed = self.samples[-1].spans_closed - self.samples[0].spans_closed
        return started, closed

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata,
            "samples": [
                {
                    "timestamp": sample.timestamp.isoformat().replace("+00:00", "Z"),
                    "rss_bytes": sample.rss_bytes,
                    "container_restarts": sample.container_restarts,
                    "spans_started": sample.spans_started,
                    "spans_closed": sample.spans_closed,
                }
                for sample in self.samples
            ],
        }


@dataclass(slots=True)
class SoakReport:
    """Structured outcome emitted after evaluation."""

    passed: bool
    duration_hours: float
    span_closure_ratio: float
    span_deficit: int
    container_restarts: int
    rss_drift_bytes: int
    rss_min_bytes: int
    rss_max_bytes: int
    sample_count: int
    violations: list[str]

    def to_gate_payload(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "duration_hours": round(self.duration_hours, 3),
            "span_closure_ratio": self.span_closure_ratio,
            "span_deficit": self.span_deficit,
            "container_restarts": self.container_restarts,
            "rss_drift_bytes": self.rss_drift_bytes,
            "rss_min_bytes": self.rss_min_bytes,
            "rss_max_bytes": self.rss_max_bytes,
            "sample_count": self.sample_count,
            "violations": self.violations,
        }


class SoakAnalyzer:
    """Evaluate soak runs against ``SoakConfig`` thresholds."""

    def __init__(self, config: SoakConfig) -> None:
        self._config = config

    def evaluate(self, run: SoakRun) -> SoakReport:
        started, closed = run.span_totals()
        ratio = 1.0 if started == 0 else closed / started
        span_deficit = max(started - closed, 0)

        violations: list[str] = []
        if run.duration_hours < self._config.min_duration_hours:
            violations.append(
                f"duration {run.duration_hours:.2f}h below minimum {self._config.min_duration_hours:.2f}h"
            )
        if run.container_restart_delta > self._config.max_container_restarts:
            violations.append(
                "container restarts exceeded budget"
            )
        if span_deficit:
            violations.append(
                f"{span_deficit} spans missing closure"
            )
        if run.rss_drift > self._config.rss_drift_budget_bytes:
            violations.append(
                "rss drift exceeds budget"
            )

        passed = not violations
        return SoakReport(
            passed=passed,
            duration_hours=run.duration_hours,
            span_closure_ratio=ratio,
            span_deficit=span_deficit,
            container_restarts=run.container_restart_delta,
            rss_drift_bytes=run.rss_drift,
            rss_min_bytes=run.rss_min,
            rss_max_bytes=run.rss_max,
            sample_count=len(run.samples),
            violations=violations,
        )


def load_soak_run(path: Path) -> tuple[SoakRun, SoakConfig]:
    """Load soak dataset and configuration from *path*."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    config_payload = payload.get("config")
    if not isinstance(config_payload, dict):
        raise ValueError("soak dataset must include configuration mapping under 'config'")
    config = SoakConfig.from_dict(config_payload)
    run = SoakRun.from_dict(payload)
    return run, config


def evaluate_soak_file(path: Path) -> SoakReport:
    """Convenience helper returning the soak report for *path*."""

    run, config = load_soak_run(path)
    analyzer = SoakAnalyzer(config)
    return analyzer.evaluate(run)


def iter_reports(paths: Iterable[Path]) -> list[SoakReport]:
    """Evaluate multiple soak datasets and return their reports."""

    reports: list[SoakReport] = []
    for path in paths:
        reports.append(evaluate_soak_file(path))
    return reports