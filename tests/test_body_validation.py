from dataclasses import dataclass

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
    assert err["detail"][0]["loc"] == ["body", "price"]

    missing = client.request(
        "POST",
        "/items",
        params={"count": 2, "ratio": 1.5, "active": True},
        json_body={"price": 3.5},
    )
    assert missing.status_code == 422
    miss = missing.json()
    assert miss["detail"][0]["loc"] == ["body", "name"]
    assert miss["detail"][0]["msg"] == "Field required"