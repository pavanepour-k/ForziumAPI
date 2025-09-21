"""Regression tests for :mod:`forzium.testclient`."""

from __future__ import annotations

from forzium import ForziumApp
from forzium.testclient import TestClient


def test_testclient_matches_path_params() -> None:
    app = ForziumApp()

    @app.get("/items/{item_id}")
    def read_item(item_id: str) -> dict[str, str]:
        return {"item_id": item_id}

    client = TestClient(app)
    response = client.get("/items/123")

    assert response.status_code == 200
    assert response.json() == {"item_id": "123"}