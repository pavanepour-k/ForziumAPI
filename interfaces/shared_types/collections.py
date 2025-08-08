"""Collection-based shared types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class Matrix:
    """FFI-safe matrix representation."""

    rows: List[List[float]]

    @classmethod
    def from_rust(cls, rows: List[List[float]]) -> "Matrix":
        """Build a matrix from Rust data."""
        return cls(rows)

    def to_rust(self) -> List[List[float]]:
        """Return a Rust-friendly structure."""
        return self.rows
