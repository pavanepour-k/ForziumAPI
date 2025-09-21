from pydantic import BaseModel

from forzium import ForziumApp, TestClient


class Item(BaseModel):
    name: str
    qty: int


def test_pydantic_model_body_parsed() -> None:
    app = ForziumApp()

    @app.post("/items")
    def create_item(item: Item) -> dict[str, int | str]:
        assert isinstance(item, Item)
        return {"name": item.name, "qty": item.qty}

    client = TestClient(app)
    resp = client.request(
        "POST",
        "/items",
        json_body={"name": "apple", "qty": 5},
    )
    assert resp.status_code == 200
    assert resp.json() == {"name": "apple", "qty": 5}

    bad = client.request(
        "POST",
        "/items",
        json_body={"name": "apple", "qty": "five"},
    )
    assert bad.status_code == 422
    body = bad.json()
    detail = body["detail"][0]
    assert detail["loc"] == ["body", "qty"]
    assert detail.get("url") is None
    assert detail["input"] == "five"