"""Tests for machine learning inference bindings."""

import pytest

from forzium_engine import LinearModel


def test_linear_model_prediction(tmp_path) -> None:
    model_file = tmp_path / "model.txt"
    model_file.write_text("1 2 3")
    model = LinearModel.load(str(model_file))
    assert model.predict([4.0, 5.0]) == pytest.approx(24.0)


def test_linear_model_shape_error(tmp_path) -> None:
    model_file = tmp_path / "model.txt"
    model_file.write_text("0 1 2")
    model = LinearModel.load(str(model_file))
    with pytest.raises(RuntimeError):
        model.predict([1.0])


def test_missing_model() -> None:
    with pytest.raises(RuntimeError):
        LinearModel.load("no_file.txt")
