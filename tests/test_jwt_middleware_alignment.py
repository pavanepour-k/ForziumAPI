"""Integration tests verifying JWT middleware parameter alignment."""

from __future__ import annotations

from forzium import ForziumApp, TestClient
from forzium.middleware import JWTMiddleware
from forzium.security import create_jwt


def test_jwt_middleware_preserves_path_param_alignment() -> None:
    app = ForziumApp()
    app.add_middleware(JWTMiddleware, secret="secret")

    observed: list[tuple[object, object]] = []

    @app.get("/items/{item_id:int}")
    def read_item(item_id: int, user) -> dict[str, object]:
        observed.append((user, item_id))
        return {"user": user, "item_id": item_id}

    client = TestClient(app)

    token_with_dict = create_jwt({"user": {"name": "alice"}}, "secret")
    response_dict = client.get("/items/7", params={"token": token_with_dict})
    assert response_dict.status_code == 200
    assert response_dict.json() == {"user": {"name": "alice"}, "item_id": 7}

    token_with_str = create_jwt({"user": "bob"}, "secret")
    response_str = client.get("/items/9", params={"token": token_with_str})
    assert response_str.status_code == 200
    assert response_str.json() == {"user": "bob", "item_id": 9}

    assert observed == [({"name": "alice"}, 7), ("bob", 9)]
    assert all(isinstance(item_id, int) for _, item_id in observed)
    assert isinstance(observed[0][0], dict)
    assert isinstance(observed[1][0], str)