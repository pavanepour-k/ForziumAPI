"""Verify basic content negotiation and error handling."""

from forzium.app import ForziumApp
from forzium.responses import HTTPException
from forzium.testclient import TestClient


def test_plain_text_preferred_via_accept() -> None:
    app = ForziumApp()

    @app.get("/greet")
    def greet() -> str:
        return "hello"

    client = TestClient(app)
    resp = client.get("/greet", headers={"accept": "text/plain"})
    assert resp.status_code == 200
    assert resp.text == "hello"
    assert resp.headers["content-type"].startswith("text/plain")


def test_http_exception_serialized() -> None:
    app = ForziumApp()

    @app.get("/fail")
    def fail() -> None:
        raise HTTPException(418, "nope")

    client = TestClient(app)
    resp = client.get("/fail")
    assert resp.status_code == 418
    assert resp.json() == {"detail": "nope"}


def test_unhandled_exception_returns_500() -> None:
    app = ForziumApp()

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("bad")

    client = TestClient(app)
    resp = client.get("/boom")
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Internal Server Error"


def test_quality_value_selection() -> None:
    app = ForziumApp()

    @app.get("/hello")
    def hello() -> str:
        return "hi"

    client = TestClient(app)
    hdr = {"accept": "text/plain;q=0.3, application/json;q=0.9"}
    resp = client.get("/hello", headers=hdr)
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json() == "hi"


def test_not_acceptable() -> None:
    app = ForziumApp()

    @app.get("/hi")
    def hi() -> str:
        return "hi"

    client = TestClient(app)
    resp = client.get("/hi", headers={"accept": "application/xml"})
    assert resp.status_code == 406