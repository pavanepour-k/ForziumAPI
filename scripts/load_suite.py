"""Scenario loading and synthetic execution utilities for load generators."""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping, MutableMapping, Sequence


@dataclass(slots=True)
class PlanEntry:
    """Concrete request scheduled for execution within a scenario."""

    sequence: int
    stage: str
    offset_s: float
    include_in_metrics: bool
    demand_rps: float | None = None


@dataclass(slots=True)
class ScenarioPlan:
    """Ordered list of :class:`PlanEntry` objects representing the scenario."""

    entries: list[PlanEntry] = field(default_factory=list)
    total_duration_s: float = 0.0

    def __post_init__(self) -> None:  # pragma: no cover - simple normalisation
        self.total_duration_s = float(self.total_duration_s)


class _ParameterSampler:
    """Interface implemented by parameter sampling strategies."""

    def sample(self) -> Any:  # pragma: no cover - interface
        raise NotImplementedError


class _SequentialSampler(_ParameterSampler):
    def __init__(self, start: int = 0, step: int = 1) -> None:
        self._next = start
        self._step = step

    def sample(self) -> int:
        value = self._next
        self._next += self._step
        return value


class _ZipfSampler(_ParameterSampler):
    """Zipfian sampler with deterministic RNG."""

    def __init__(self, size: int, exponent: float, seed: int) -> None:
        self._rng = random.Random(seed)
        weights = [1.0 / math.pow(index + 1, max(exponent, 0.1)) for index in range(max(size, 1))]
        total = sum(weights)
        cumulative: list[float] = []
        running = 0.0
        for weight in weights:
            running += weight / total if total else 0.0
            cumulative.append(running)
        self._cumulative = cumulative

    def sample(self) -> int:
        roll = self._rng.random()
        for index, threshold in enumerate(self._cumulative):
            if roll <= threshold:
                return index
        return max(len(self._cumulative) - 1, 0)


class _TenantAllocator:
    """Resolve tenant headers for scheduled requests."""

    def __init__(
        self,
        header: str | None,
        distribution: Sequence[tuple[str, float]] | None,
        rotation: tuple[list[str], float] | None,
        seed: int,
    ) -> None:
        self._header = header
        self._distribution = distribution
        self._rotation = rotation
        self._rng = random.Random(seed)

    def choose(self, offset_s: float, sequence: int) -> tuple[str | None, str | None]:
        if self._header is None:
            return None, None
        if self._rotation:
            sequence_values, cycle_seconds = self._rotation
            if not sequence_values:
                return self._header, None
            if cycle_seconds <= 0:
                index = sequence % len(sequence_values)
            else:
                cycle_position = (offset_s % cycle_seconds) / cycle_seconds
                index = int(cycle_position * len(sequence_values)) % len(sequence_values)
            return self._header, sequence_values[index]
        if self._distribution:
            choices, weights = zip(*self._distribution)
            total = sum(weights) or 1.0
            roll = self._rng.random() * total
            cumulative = 0.0
            for choice, weight in self._distribution:
                cumulative += weight
                if roll <= cumulative:
                    return self._header, choice
            return self._header, choices[-1]
        return self._header, None


class _RequestTemplate:
    """Materialise HTTP request payloads and paths from templates."""

    def __init__(
        self,
        method: str,
        path_template: str,
        payload_size: int,
        payload_distribution: str,
        path_params: Mapping[str, Mapping[str, Any]] | None,
        traffic_seed: int,
        payload_seed: int,
    ) -> None:
        self.method = method.upper()
        self._path_template = path_template
        self._payload_size = max(int(payload_size), 0)
        self._payload_distribution = payload_distribution or "fixed"
        self._payload_rng = random.Random(payload_seed)
        self._param_samplers: dict[str, _ParameterSampler] = {}
        if path_params:
            for index, (name, definition) in enumerate(path_params.items()):
                sampler = self._build_param_sampler(name, definition, traffic_seed + index)
                self._param_samplers[name] = sampler

    @staticmethod
    def _build_param_sampler(
        name: str, definition: Mapping[str, Any], seed: int
    ) -> _ParameterSampler:
        distribution = (definition.get("distribution") or "sequential").lower()
        params = definition.get("parameters", {})
        if distribution == "sequential":
            start = int(params.get("start", 0))
            step = int(params.get("step", 1))
            return _SequentialSampler(start=start, step=step)
        if distribution == "zipf":
            size = int(params.get("size", 1))
            exponent = float(params.get("s", 1.0))
            return _ZipfSampler(size=size, exponent=exponent, seed=seed)
        return _SequentialSampler(start=int(params.get("start", 0)))

    def resolve_path(self, sequence: int) -> tuple[str, MutableMapping[str, Any]]:
        values: dict[str, Any] = {}
        for name, sampler in self._param_samplers.items():
            values[name] = sampler.sample()
        path = self._path_template
        for name, value in values.items():
            path = path.replace(f"{{{name}}}", str(value))
        return path, values

    def build_payload(self, sequence: int) -> Mapping[str, Any] | None:
        if self.method == "GET" or self._payload_size <= 0:
            return None
        size = self._resolve_payload_size()
        blob = self._generate_blob(size)
        return {"sequence": sequence, "blob": blob}

    def _resolve_payload_size(self) -> int:
        distribution = self._payload_distribution.lower()
        if distribution == "fixed":
            return self._payload_size
        if distribution == "lognormal":
            return max(1, int(self._payload_rng.lognormvariate(math.log(self._payload_size or 1), 0.25)))
        if distribution == "gamma":
            shape = max(self._payload_size / 8.0, 1.0)
            scale = max(self._payload_size / shape, 1.0)
            return max(1, int(self._payload_rng.gammavariate(shape, scale)))
        if distribution == "mixture":
            if self._payload_rng.random() < 0.5:
                return self._payload_size
            return max(1, int(self._payload_rng.expovariate(1.0 / max(self._payload_size, 1))))
        return self._payload_size

    def _generate_blob(self, size: int) -> str:
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return "".join(self._payload_rng.choice(alphabet) for _ in range(size))


@dataclass(slots=True)
class LoadScenarioDefinition:
    """Scenario definition capable of producing executable plans."""

    identifier: str
    name: str
    pattern: Mapping[str, Any]
    concurrency: int
    request: _RequestTemplate
    tenant_allocator: _TenantAllocator
    warmup_duration_s: float = 0.0
    warmup_discard_metrics: bool = True

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LoadScenarioDefinition":
        identifier = data.get("id") or data.get("name")
        if not identifier:
            raise ValueError("Scenario definition missing 'id' or 'name'")
        pattern = data.get("pattern") or {}
        concurrency = int(data.get("concurrency", 1))
        seed_info = data.get("seed", {})
        traffic_seed = int(seed_info.get("traffic", 1))
        payload_seed = int(seed_info.get("payload", traffic_seed + 17))
        request_template = _RequestTemplate(
            method=(data.get("request") or {}).get("method", "GET"),
            path_template=(data.get("request") or {}).get("path", "/"),
            payload_size=(data.get("request") or {}).get("payload_size_bytes", 0),
            payload_distribution=(data.get("request") or {}).get("payload_distribution", "fixed"),
            path_params=(data.get("request") or {}).get("path_params"),
            traffic_seed=traffic_seed,
            payload_seed=payload_seed,
        )
        tenants = data.get("tenants") or {}
        header = tenants.get("header")
        distribution = None
        if isinstance(tenants.get("distribution"), list):
            distribution = [
                (str(item.get("tenant", "default")), float(item.get("weight", 1.0)))
                for item in tenants["distribution"]
            ]
        rotation = None
        if isinstance(tenants.get("rotation_order"), Mapping):
            sequence = [str(value) for value in tenants["rotation_order"].get("sequence", [])]
            cycle = float(tenants["rotation_order"].get("cycle_seconds", 1.0))
            rotation = (sequence, cycle)
        tenant_allocator = _TenantAllocator(header, distribution, rotation, traffic_seed + 101)
        warmup = data.get("warmup") or {}
        warmup_duration = float(warmup.get("duration_s", 0.0))
        discard_metrics = bool(warmup.get("discard_metrics", True))
        return cls(
            identifier=str(identifier),
            name=str(data.get("name", identifier)),
            pattern=pattern,
            concurrency=concurrency,
            request=request_template,
            tenant_allocator=tenant_allocator,
            warmup_duration_s=warmup_duration,
            warmup_discard_metrics=discard_metrics,
        )

    @property
    def pattern_type(self) -> str:
        return str(self.pattern.get("type", "steady")).lower()

    def build_plan(
        self,
        *,
        duration_scale: float = 1.0,
        max_requests: int | None = None,
        ramp_resolution: float | None = None,
    ) -> ScenarioPlan:
        remaining = max_requests if max_requests is not None else float("inf")
        entries: list[PlanEntry] = []
        sequence = 0
        offset = 0.0
        if self.warmup_duration_s > 0 and remaining > 0:
            entries.append(
                PlanEntry(
                    sequence=sequence,
                    stage="warmup",
                    offset_s=offset,
                    include_in_metrics=not self.warmup_discard_metrics,
                    demand_rps=None,
                )
            )
            remaining -= 1
            sequence += 1
            offset += self.warmup_duration_s * duration_scale
        if remaining <= 0:
            return ScenarioPlan(entries=entries, total_duration_s=offset)
        pattern_type = self.pattern_type
        builder = {
            "steady": self._build_steady,
            "poisson": self._build_poisson,
            "burst": self._build_burst,
            "ramp": self._build_ramp,
        }.get(pattern_type, self._build_steady)
        generated, final_offset = builder(
            sequence_start=sequence,
            start_offset=offset,
            remaining=int(remaining if remaining != float("inf") else 10**9),
            duration_scale=duration_scale,
            ramp_resolution=ramp_resolution or 8.0,
        )
        entries.extend(generated)
        total_duration = final_offset if generated else offset
        if max_requests is not None and len(entries) > max_requests:
            entries = entries[:max_requests]
        return ScenarioPlan(entries=entries, total_duration_s=total_duration)

    # Stage builders -----------------------------------------------------------------

    def _build_steady(
        self,
        *,
        sequence_start: int,
        start_offset: float,
        remaining: int,
        duration_scale: float,
        ramp_resolution: float,
    ) -> tuple[list[PlanEntry], float]:
        pattern = self.pattern
        duration = float(pattern.get("duration_s", 0.0)) * duration_scale
        target_rps = float(pattern.get("target_rps", 0.0))
        return self._constant_stage(
            stage_name=self.pattern_type,
            sequence_start=sequence_start,
            start_offset=start_offset,
            duration=duration,
            target_rps=target_rps,
            include_in_metrics=True,
            remaining=remaining,
        )

    def _build_poisson(
        self,
        *,
        sequence_start: int,
        start_offset: float,
        remaining: int,
        duration_scale: float,
        ramp_resolution: float,
    ) -> tuple[list[PlanEntry], float]:
        pattern = self.pattern
        duration = float(pattern.get("duration_s", 0.0)) * duration_scale
        lambda_rps = float(pattern.get("lambda_rps", 0.0))
        if duration <= 0 or lambda_rps <= 0:
            return [], start_offset
        rng = random.Random(self.concurrency * 7919 + sequence_start)
        entries: list[PlanEntry] = []
        elapsed = 0.0
        sequence = sequence_start
        while elapsed < duration and len(entries) < remaining:
            elapsed += rng.expovariate(lambda_rps)
            if elapsed >= duration:
                break
            entries.append(
                PlanEntry(
                    sequence=sequence,
                    stage=self.pattern_type,
                    offset_s=start_offset + elapsed,
                    include_in_metrics=True,
                    demand_rps=lambda_rps,
                )
            )
            sequence += 1
        final_offset = start_offset + duration
        return entries, final_offset

    def _build_burst(
        self,
        *,
        sequence_start: int,
        start_offset: float,
        remaining: int,
        duration_scale: float,
        ramp_resolution: float,
    ) -> tuple[list[PlanEntry], float]:
        pattern = self.pattern
        stages = pattern.get("stages") or []
        entries: list[PlanEntry] = []
        offset = start_offset
        sequence = sequence_start
        for stage in stages:
            duration = float(stage.get("duration_s", 0.0)) * duration_scale
            target_rps = float(stage.get("target_rps", 0.0))
            stage_entries, offset = self._constant_stage(
                stage_name=self.pattern_type,
                sequence_start=sequence,
                start_offset=offset,
                duration=duration,
                target_rps=target_rps,
                include_in_metrics=True,
                remaining=remaining - len(entries),
            )
            entries.extend(stage_entries)
            sequence += len(stage_entries)
            if len(entries) >= remaining:
                break
        final_offset = offset
        return entries, final_offset

    def _build_ramp(
        self,
        *,
        sequence_start: int,
        start_offset: float,
        remaining: int,
        duration_scale: float,
        ramp_resolution: float,
    ) -> tuple[list[PlanEntry], float]:
        pattern = self.pattern
        phases = pattern.get("phases") or []
        entries: list[PlanEntry] = []
        offset = start_offset
        sequence = sequence_start
        segments_per_second = max(ramp_resolution, 1.0)
        for phase in phases:
            duration = float(phase.get("duration_s", 0.0)) * duration_scale
            start_rps = float(phase.get("start_rps", 0.0))
            end_rps = float(phase.get("end_rps", start_rps))
            if duration <= 0:
                continue
            segments = max(1, int(round(duration * segments_per_second)))
            segment_duration = duration / segments
            for index in range(segments):
                if len(entries) >= remaining:
                    break
                fraction = (index + 0.5) / segments
                instantaneous_rps = start_rps + (end_rps - start_rps) * fraction
                stage_entries, offset = self._constant_stage(
                    stage_name=self.pattern_type,
                    sequence_start=sequence,
                    start_offset=offset,
                    duration=segment_duration,
                    target_rps=instantaneous_rps,
                    include_in_metrics=True,
                    remaining=remaining - len(entries),
                )
                entries.extend(stage_entries)
                sequence += len(stage_entries)
            if len(entries) >= remaining:
                break
        final_offset = offset
        return entries, final_offset

    def _constant_stage(
        self,
        *,
        stage_name: str,
        sequence_start: int,
        start_offset: float,
        duration: float,
        target_rps: float,
        include_in_metrics: bool,
        remaining: int,
    ) -> tuple[list[PlanEntry], float]:
        if duration <= 0 or target_rps <= 0 or remaining <= 0:
            return [], start_offset + max(duration, 0.0)
        interval = 1.0 / target_rps
        elapsed = 0.0
        sequence = sequence_start
        entries: list[PlanEntry] = []
        while elapsed < duration and len(entries) < remaining:
            entries.append(
                PlanEntry(
                    sequence=sequence,
                    stage=stage_name,
                    offset_s=start_offset + elapsed,
                    include_in_metrics=include_in_metrics,
                    demand_rps=target_rps,
                )
            )
            sequence += 1
            elapsed += interval
        final_offset = start_offset + duration
        return entries, final_offset


class LoadSuiteRunner:
    """Synthetic scenario executor used for testing and CI validation."""

    def __init__(
        self,
        scenarios: Iterable[LoadScenarioDefinition],
        *,
        service_time_ms: float,
        jitter_ms: float,
        error_profile: Mapping[str, Mapping[str, float]] | None = None,
    ) -> None:
        self._scenarios = list(scenarios)
        self._service_time_ms = max(service_time_ms, 0.1)
        self._jitter_ms = max(jitter_ms, 0.0)
        self._error_profile = {k: dict(v) for k, v in (error_profile or {}).items()}

    def run(
        self,
        *,
        duration_scale: float = 1.0,
        max_requests: int | None = None,
        ramp_resolution: float | None = None,
    ) -> Mapping[str, Any]:
        results: list[Mapping[str, Any]] = []
        for scenario in self._scenarios:
            plan = scenario.build_plan(
                duration_scale=duration_scale,
                max_requests=max_requests,
                ramp_resolution=ramp_resolution,
            )
            scenario_rng = random.Random(hash(scenario.identifier) & 0xFFFFFFFF)
            total_requests = len(plan.entries)
            included_requests = 0
            latency_samples: list[float] = []
            stage_metrics: dict[str, dict[str, Any]] = {}
            failure_modes: list[dict[str, Any]] = []
            saturation_points: list[dict[str, Any]] = []
            stage_failures = self._error_profile.get(scenario.identifier, {})
            for entry in plan.entries:
                stage_info = stage_metrics.setdefault(
                    entry.stage,
                    {
                        "requests": 0,
                        "included_requests": 0,
                        "latencies": [],
                    },
                )
                stage_info["requests"] += 1
                latency = max(
                    0.1,
                    scenario_rng.gauss(self._service_time_ms, self._jitter_ms or 0.0),
                )
                stage_info["latencies"].append(latency)
                if entry.include_in_metrics:
                    included_requests += 1
                    stage_info["included_requests"] += 1
                    latency_samples.append(latency)
                fail_rate = float(stage_failures.get(entry.stage, 0.0))
                if fail_rate > 0:
                    stage_info.setdefault("failure_rate", fail_rate)
            for stage, info in stage_metrics.items():
                latencies = info.pop("latencies", [])
                included = info.get("included_requests", 0)
                info["latency_ms"] = {
                    "mean": mean(latencies) if latencies else 0.0,
                    "p95": self._percentile(latencies, 95.0),
                }
                fail_rate = info.get("failure_rate")
                if fail_rate:
                    failure_modes.append({"stage": stage, "rate": fail_rate})
            for entry in plan.entries:
                if entry.demand_rps is None or entry.demand_rps <= 0:
                    continue
                utilisation = (
                    entry.demand_rps * self._service_time_ms / 1000.0
                ) / max(scenario.concurrency, 1)
                if utilisation > 1.0:
                    saturation_points.append(
                        {
                            "stage": entry.stage,
                            "offset_s": entry.offset_s,
                            "utilisation": utilisation,
                        }
                    )
            result = {
                "id": scenario.identifier,
                "pattern": scenario.pattern_type,
                "total_requests": total_requests,
                "included_requests": included_requests,
                "plan_duration_s": plan.total_duration_s,
                "metrics": {
                    "latency_ms": {
                        "mean": mean(latency_samples) if latency_samples else 0.0,
                        "p95": self._percentile(latency_samples, 95.0),
                    }
                },
                "stage_metrics": stage_metrics,
                "failure_modes": failure_modes,
                "saturation_points": saturation_points,
            }
            results.append(result)
        return {"scenarios": results}

    @staticmethod
    def _percentile(samples: Sequence[float], percentile: float) -> float:
        if not samples:
            return 0.0
        ordered = sorted(samples)
        k = (len(ordered) - 1) * percentile / 100.0
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return ordered[int(k)]
        d0 = ordered[int(f)] * (c - k)
        d1 = ordered[int(c)] * (k - f)
        return d0 + d1


def load_scenarios(path: str | Path, *, only: Sequence[str] | None = None) -> list[LoadScenarioDefinition]:
    """Load scenario definitions from ``path``."""

    file_path = Path(path)
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    if isinstance(raw, Mapping) and "scenarios" in raw:
        scenarios_data = raw["scenarios"]
    elif isinstance(raw, list):
        scenarios_data = raw
    else:
        raise ValueError("Invalid scenario document; expected list or {\"scenarios\": [...]} structure")
    definitions = [LoadScenarioDefinition.from_dict(item) for item in scenarios_data]
    if only:
        selector = {value for value in only}
        definitions = [
            scenario
            for scenario in definitions
            if scenario.identifier in selector or scenario.name in selector
        ]
    return definitions


__all__ = [
    "LoadScenarioDefinition",
    "PlanEntry",
    "ScenarioPlan",
    "LoadSuiteRunner",
    "load_scenarios",
]