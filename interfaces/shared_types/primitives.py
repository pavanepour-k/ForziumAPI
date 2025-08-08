"""Primitive shared types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Float64:
    """FFI-safe wrapper around a floating point value."""

    value: float

    @classmethod
    def from_rust(cls, val: float) -> "Float64":
        """Create from a Rust primitive."""
        return cls(val)

    def to_rust(self) -> float:
        """Return the inner value for Rust FFI."""
        return self.value
