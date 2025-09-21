"""Ensure security headers and CORS configuration."""

from forzium import ForziumApp
from forzium.middleware import CORSMiddleware, SecurityHeadersMiddleware
from forzium.testclient import TestClient


def test_security_headers_and_cors() -> None:
    app = ForziumApp()
    app.add_middleware(
        CORSMiddleware,
        allow_origin="https://example.com",
        allow_methods="GET,POST",
        allow_headers="x-custom",
        allow_credentials=True,
        max_age=10,
    )
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/")
    def index():
        return {"ok": True}

    client = TestClient(app)
    resp = client.get("/")
    headers = resp.headers
    assert headers["access-control-allow-origin"] == "https://example.com"
    assert headers["access-control-allow-methods"] == "GET,POST"
    assert headers["access-control-allow-headers"] == "x-custom"
    assert headers["access-control-allow-credentials"] == "true"
    assert headers["access-control-max-age"] == "10"
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["x-xss-protection"] == "1; mode=block"
    assert headers["referrer-policy"] == "same-origin"