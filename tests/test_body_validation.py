from dataclasses import dataclass

import pytest

from forzium import ForziumApp
from forzium.testclient import TestClient


@dataclass
class Item:
    name: str
    price: float
    in_stock: bool = True


def test_body_and_query_coercion() -> None:
    app = ForziumApp()

    @app.post("/items")
    def create(item: Item, count: int, ratio: float, active: bool):
        return {
            "item": item.__dict__,
            "count": count,
            "ratio": ratio,
            "active": active,
        }

    client = TestClient(app)
    resp = client.request(
        "POST",
        "/items",
        params={"count": 2, "ratio": 1.5, "active": True},
        json_body={"name": "apple", "price": 3.5},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "item": {"name": "apple", "price": 3.5, "in_stock": True},
        "count": 2,
        "ratio": 1.5,
        "active": True,
    }

    bad = client.request(
        "POST",
        "/items",
        params={"count": 2, "ratio": 1.5, "active": True},
        json_body={"name": "apple", "price": "cheap"},
    )
    assert bad.status_code == 422
    err = bad.json()
    detail = err["detail"][0]
    assert detail["loc"] == ["body", "price"]
    assert detail["msg"] == "value is not a valid float"
    assert detail["type"] == "float_parsing"

    missing = client.request(
        "POST",
        "/items",
        params={"count": 2, "ratio": 1.5, "active": True},
        json_body={"price": 3.5},
    )
    assert missing.status_code == 422
    miss = missing.json()
    miss_detail = miss["detail"][0]
    assert miss_detail["loc"] == ["body", "name"]
    assert miss_detail["msg"] == "Field required"

    bad_count = client.request(
        "POST",
        "/items",
        params={"count": "two", "ratio": 1.5, "active": True},
        json_body={"name": "apple", "price": 3.5},
    )
    assert bad_count.status_code == 422
    count_detail = bad_count.json()["detail"][0]
    assert count_detail["loc"] == ["query", "count"]
    assert count_detail["msg"] == "value is not a valid integer"
    assert count_detail["type"] == "int_parsing"

    bad_bool = client.request(
        "POST",
        "/items",
        params={"count": 2, "ratio": 1.5, "active": "maybe"},
        json_body={"name": "apple", "price": 3.5},
    )
    assert bad_bool.status_code == 422
    bool_detail = bad_bool.json()["detail"][0]
    assert bool_detail["loc"] == ["query", "active"]
    assert bool_detail["msg"] == "value is not a valid boolean"
    assert bool_detail["type"] == "bool_parsing"


def test_type_adapter_error_canonicalization(monkeypatch: pytest.MonkeyPatch) -> None:
    from forzium.app import RequestValidationError, _validate_with_type_adapter

    class FakeValidationError(Exception):
        def errors(self) -> list[dict[str, object]]:
            return [
                {
                    "loc": ("__root__",),
                    "msg": "Input should be a valid integer, unable to parse string as an integer",
                    "type": "type_error.integer",
                    "input": "bad",
                }
            ]

    class FakeAdapter:
        def validate_python(self, value: object) -> object:
            raise FakeValidationError from None

    monkeypatch.setattr("forzium.app._get_type_adapter", lambda tp: FakeAdapter())
    monkeypatch.setattr("forzium.app.PydanticValidationError", FakeValidationError)

    with pytest.raises(RequestValidationError) as excinfo:
        _validate_with_type_adapter("bad", int, ["body", "qty"])

    (error,) = excinfo.value.errors()
    assert error["loc"] == ["body", "qty"]
    assert error["msg"] == "value is not a valid integer"
    assert error["type"] == "int_parsing"
    assert error["input"] == "bad"