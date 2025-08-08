"""Tests for custom validation utilities replacing Pydantic."""

import pytest

from interfaces.pydantic_compat import (
    BaseModel,
    field_validator,
    model_validator,
)


class Demo(BaseModel):
    """Model using validators and defaults."""

    x: int
    y: int = 5

    @model_validator(mode="before")
    def cast(cls, values: dict[str, object]) -> dict[str, object]:
        values["x"] = int(values["x"])
        return values

    @field_validator("x")
    def check_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("x must be positive")
        return v


def test_custom_model_validates() -> None:
    m = Demo(x="1")
    assert m.x == 1
    assert m.y == 5
    assert m.dict() == {"x": 1, "y": 5}


def test_field_validator_error_message() -> None:
    with pytest.raises(ValueError) as exc:
        Demo(x="-1")
    assert str(exc.value) == "x must be positive"


def test_missing_field_error() -> None:
    with pytest.raises(ValueError) as exc:
        Demo()
    assert str(exc.value) == "Field required"


def test_model_json_schema() -> None:
    assert Demo.model_json_schema() == {
        "title": "Demo",
        "type": "object",
        "properties": {
            "x": {"type": "integer"},
            "y": {"type": "integer", "default": 5},
        },
        "required": ["x"],
    }
