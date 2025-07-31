"""Models validated using the Rust engine."""

from typing import Any, Dict
from fastapi import Body
from forzium import ComputeRequest as RustComputeRequest


class ComputeRequest(RustComputeRequest):
    """ComputeRequest backed by Rust validator."""

    @classmethod
    def as_body(cls) -> Dict[str, Any]:
        return Body(...)