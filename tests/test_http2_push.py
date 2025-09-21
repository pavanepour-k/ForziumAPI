"""Test simulated HTTP/2 server push."""

import json
import logging

import pytest

from forzium import ForziumApp, push


class DummyServer:
    def add_route(self, method: str, path: str, handler):
        self.handler = handler


def test_push_header(caplog: pytest.LogCaptureFixture) -> None:
    srv = DummyServer()
    app = ForziumApp(srv)

    @app.get("/")
    def home():
        push("/style.css")
        return {"ok": True}

    route = next(r for r in app.routes if r["path"] == "/" and r["func"].__name__ == "home")
    handler = app._make_handler(
        route["func"],
        route["param_names"],
        route["param_converters"],
        route["query_params"],
        route["expects_body"],
        route["dependencies"],
    )
    with caplog.at_level(logging.INFO, logger="forzium.observability"):
        status, body, headers = handler(b"", tuple(), b"")
    assert status == 200
    normalized = {key.lower(): value for key, value in headers.items()}
    assert normalized["link"] == "</style.css>; rel=preload"
    record = caplog.records[-1]
    payload = json.loads(record.msg)
    assert payload["event"] == "http2.push"
    assert payload["count"] == 1
    assert payload["applied_at"] is not None
    entry = payload["hints"][0]
    assert entry["path"] == "/style.css"
    assert entry["registered_at"] is not None
    assert entry["ms_until_apply"] >= 0


def test_push_rejects_blank_path() -> None:
    with pytest.raises(ValueError):
        push("   ")