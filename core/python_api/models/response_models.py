from dataclasses import dataclass, asdict
from typing import List


@dataclass
class ComputeResponse:
    """Response returned from compute endpoints."""

    result: List[List[float]]
    execution_time_ms: float
    memory_usage_mb: float
    rust_operations_count: int

    def dict(self) -> dict:
        """Return dictionary representation."""
        return asdict(self)