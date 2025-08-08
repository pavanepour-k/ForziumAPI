"""Verify interactive documentation endpoints."""

from forzium import ForziumApp, TestClient


def test_docs_endpoints() -> None:
    app = ForziumApp()

    @app.get("/items")
    def items() -> list[str]:
        return ["a"]

    client = TestClient(app)
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert "swagger-ui" in resp.text.lower()
    resp = client.get("/redoc")
    assert resp.status_code == 200
    assert "redoc" in resp.text.lower()
