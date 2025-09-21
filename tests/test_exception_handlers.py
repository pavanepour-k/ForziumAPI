"""Ensure custom exception handlers override defaults."""

from forzium.app import ForziumApp
from forzium.testclient import TestClient
from forzium.responses import HTTPException
from forzium.dependency import Request


def test_custom_handler_used() -> None:
    app = ForziumApp()

    def handle_value_error(request: Request, exc: ValueError):
        return 422, "bad value", {"x": "y"}

    app.add_exception_handler(ValueError, handle_value_error)

    @app.get("/boom")
    def boom() -> None:
        raise ValueError("nope")

    client = TestClient(app)
    resp = client.get("/boom")
    assert resp.status_code == 422
    assert resp.text == "bad value"
    assert resp.headers["x"] == "y"


def test_handler_overrides_http_exception() -> None:
    app = ForziumApp()

    def handle_http_exc(request: Request, exc: HTTPException):
        return 499, {"detail": "handled"}, {}

    app.add_exception_handler(HTTPException, handle_http_exc)

    @app.get("/fail")
    def fail() -> None:
        raise HTTPException(400, "orig")

    client = TestClient(app)
    resp = client.get("/fail")
    assert resp.status_code == 499
    assert resp.json() == {"detail": "handled"}