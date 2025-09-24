"""Test stub for the Rust-backed forzium_engine package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass
class ComputeRequestSchema:
    """Stub schema mimicking the validation contract of the Rust extension.

    The real extension validates payloads at the Rust level. For unit tests
    that only exercise version synchronization, we provide a minimal schema
    that performs identity validation while ensuring required keys exist.
    """

    required_keys: tuple[str, ...] = ("data", "operation")

    def validate(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        missing = [key for key in self.required_keys if key not in payload]
        if missing:
            raise ValueError(
                f"Missing keys for compute request validation: {missing}"
            )
        data = payload.get("data")
        if not isinstance(data, list) or not data:
            raise ValueError("Data must be a non-empty rectangular matrix")
        row_len = len(data[0])
        for row in data:
            if not isinstance(row, list) or len(row) != row_len:
                raise ValueError("Data must be a non-empty rectangular matrix")
        if "parameters" not in payload:
            payload = dict(payload)
            payload.setdefault("parameters", {})
        return payload