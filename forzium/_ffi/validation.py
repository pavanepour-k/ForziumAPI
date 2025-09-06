"""Python wrappers around Rust validation schemas."""

import json
from typing import Any

from forzium_engine import ComputeRequestSchema


class ComputeRequest:
    """Python wrapper for Rust-based ComputeRequest validation."""

    _schema = ComputeRequestSchema()

    def __init__(self, **data: object) -> None:
        validated = self._schema.validate(data)
        self.data = validated["data"]
        self.operation = validated["operation"]
        self.parameters = validated["parameters"]

    def dict(self) -> dict[str, Any]:
        return {
            "data": self.data,
            "operation": self.operation,
            "parameters": self.parameters,
        }

    def json(self) -> str:
        return json.dumps(self.dict())
