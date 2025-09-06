"""Pydantic model bridging to Rust validation."""

from __future__ import annotations

from dataclasses import field

from forzium._ffi.validation import ComputeRequest
from interfaces.pydantic_compat import BaseModel, model_validator

class ComputeRequestModel(BaseModel):
    """Validate compute requests through the Rust schema."""

    data: list[list[float]]
    operation: str
    parameters: dict[str, object] = field(default_factory=dict)

    @classmethod
    @model_validator(mode="before")
    def rust_validate(cls, values: dict[str, object]) -> dict[str, object]:
        """Delegate validation to the Rust schema."""
        return ComputeRequest(**values).dict()
