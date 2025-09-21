"""Utilities for deterministic response normalization across parity tests."""

from __future__ import annotations

import difflib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TRANSIENT_HEADERS: tuple[str, ...] = (
    "content-length",
    "date",
    "server",
    "connection",
)

ID_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "id",
        "identifier",
        "request_id",
        "trace_id",
        "span_id",
        "correlation_id",
    }
)

TIMESTAMP_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "timestamp",
        "created_at",
        "updated_at",
        "last_seen",
        "expires_at",
        "queued_at",
        "completed_at",
    }
)

ISO8601_RE = re.compile(
    r"^(?:\d{4}-\d{2}-\d{2})(?:[Tt ]\d{2}:\d{2}:\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?$"
)
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

ARTIFACT_ROOT = Path(__file__).resolve().parent / ".artifacts"


@dataclass
class _NormalizerState:
    """Track contextual information while normalizing nested payloads."""

    identifier_map: dict[str, str] = field(default_factory=dict)
    next_identifier: int = 1

    def canonical_identifier(self, value: Any) -> str:
        """Return a deterministic placeholder for identifier-like values."""

        key = str(value)
        if key not in self.identifier_map:
            placeholder = f"<id#{self.next_identifier}>"
            self.identifier_map[key] = placeholder
            self.next_identifier += 1
        return self.identifier_map[key]


def _looks_like_uuid(value: str) -> bool:
    return bool(UUID_RE.match(value))


def _looks_like_timestamp(value: str) -> bool:
    if ISO8601_RE.match(value):
        return True
    # Accept pure date values as timestamps to ensure deterministic parity.
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", value))


def _normalize_scalar(value: Any, *, state: _NormalizerState, key_path: tuple[str, ...]) -> Any:
    """Normalize scalar values by masking time and identifier fields."""

    last_key = key_path[-1] if key_path else ""
    lower_key = last_key.lower()

    if lower_key in ID_FIELD_NAMES or lower_key.endswith("_id"):
        return state.canonical_identifier(value)

    if isinstance(value, str):
        if lower_key in TIMESTAMP_FIELD_NAMES or _looks_like_timestamp(value):
            return "<iso8601>"
        if lower_key in {"uuid", "guid"} or _looks_like_uuid(value):
            return "<uuid>"
    return value


def _normalize_json(value: Any, *, state: _NormalizerState, key_path: tuple[str, ...]) -> Any:
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key in sorted(value.keys()):
            normalized[key] = _normalize_json(
                value[key], state=state, key_path=key_path + (str(key),)
            )
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [
            _normalize_json(item, state=state, key_path=key_path)
            for item in value
        ]
    return _normalize_scalar(value, state=state, key_path=key_path)


def normalize_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    """Return stable header maps with transient values removed."""

    normalized = {str(k).lower(): str(v) for k, v in headers.items()}
    for header in TRANSIENT_HEADERS:
        normalized.pop(header, None)
    return dict(sorted(normalized.items()))


def normalize_response(resp: Any) -> dict[str, Any]:
    """Normalize HTTP responses for cross-runtime parity assertions."""

    headers = normalize_headers(getattr(resp, "headers", {}))
    status_code = getattr(resp, "status_code")
    text = getattr(resp, "text", "")
    body: Any
    try:
        body = resp.json()
    except Exception:  # pragma: no cover - fallback for non-JSON payloads
        try:
            body = json.loads(text)
        except Exception:  # pragma: no cover - raw text fallback
            body = text

    if isinstance(body, (Mapping, Sequence)) and not isinstance(
        body, (str, bytes, bytearray)
    ):
        state = _NormalizerState()
        body = _normalize_json(body, state=state, key_path=())

    return {"status": status_code, "body": body, "headers": headers}


def _clear_artifact_files(name: str, artifact_root: Path) -> None:
    """Remove stale diff artifacts when a scenario recovers."""

    for suffix in (".actual.json", ".expected.json", ".diff.txt"):
        path = artifact_root / f"{name}{suffix}"
        if path.exists():
            path.unlink()


def ensure_snapshot_match(
    name: str,
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
    *,
    artifact_root: Path = ARTIFACT_ROOT,
) -> None:
    """Assert equality and persist human-readable diffs on failure."""

    if actual == expected:
        _clear_artifact_files(name, artifact_root)
        return

    artifact_root.mkdir(parents=True, exist_ok=True)

    actual_path = artifact_root / f"{name}.actual.json"
    expected_path = artifact_root / f"{name}.expected.json"
    diff_path = artifact_root / f"{name}.diff.txt"

    actual_text = json.dumps(actual, indent=2, sort_keys=True, ensure_ascii=False)
    expected_text = json.dumps(expected, indent=2, sort_keys=True, ensure_ascii=False)

    actual_path.write_text(actual_text + "\n")
    expected_path.write_text(expected_text + "\n")

    diff = "\n".join(
        difflib.unified_diff(
            expected_text.splitlines(),
            actual_text.splitlines(),
            fromfile="expected",
            tofile="actual",
            lineterm="",
        )
    )
    diff_path.write_text(diff + "\n")

    raise AssertionError(
        "Snapshot mismatch for '{name}'. Inspect {diff_path} for the diff.".format(
            name=name, diff_path=diff_path
        )
    )