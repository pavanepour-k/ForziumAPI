"""Pydantic model bridging to Rust validation."""
# mypy: ignore-errors

from __future__ import annotations

from dataclasses import field

from forzium._ffi.validation import ComputeRequest
from interfaces.pydantic_compat import BaseModel, model_validator


class ComputeRequestModel(BaseModel):
    """Validate compute requests through the Rust schema."""

    data: list[list[float]]
    operation: str
    parameters: dict[str, object] = field(default_factory=dict)

    @model_validator(mode="before")
    def rust_validate(
        cls: type,
        values: dict[str, object],
    ) -> dict[str, object]:  # type: ignore[misc]
        """Delegate validation to the Rust schema."""
        data = values.get("data")
        if isinstance(data, list) and data:
            first_len = len(data[0])
            if any(len(row) != first_len for row in data):
                raise ValueError(
                    "Data must be a non-empty rectangular matrix"
                )  # noqa: E501
        return ComputeRequest(**values).dict()