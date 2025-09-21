import json
import logging
from dataclasses import dataclass

from forzium import Depends, ForziumApp, RequestLoggerMiddleware, TestClient
from infrastructure import monitoring


@dataclass
class Payload:
    value: int


def provide_tag() -> str:
    return "tagged"


def test_request_creates_tracing_spans() -> None:
    app = ForziumApp()

    @app.post("/observability")
    def handle(item: Payload, limit: int, tag: str = Depends(provide_tag)) -> dict[str, int | str]:
        return {"value": item.value + limit, "tag": tag}

    client = TestClient(app)
    before = list(monitoring.get_traces())
    response = client.post("/observability", json_body={"value": 3}, params={"limit": 2})
    assert response.status_code == 200
    after = list(monitoring.get_traces())
    new_spans = after[len(before) :]
    names = [span if isinstance(span, str) else getattr(span, "name", "") for span in new_spans]
    assert any(name == "/observability" for name in names)
    assert any(name.endswith("dependency_resolution") for name in names)
    assert any(name.endswith("query_validation") for name in names)
    assert any(name.endswith("body_validation") for name in names)
    assert any(name.endswith("handler_execution") for name in names)


def test_request_logger_middleware_emits_log(caplog) -> None:
    app = ForziumApp()
    app.middleware("http")(RequestLoggerMiddleware())

    @app.get("/logged")
    def route() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    caplog.set_level(logging.INFO, logger="forzium.request")
    caplog.clear()
    response = client.get("/logged", headers={"x-request-id": "abc123"})
    assert response.status_code == 200
    entries = [record for record in caplog.records if record.name == "forzium.request"]
    assert entries, "expected a structured log entry"
    payload = json.loads(entries[0].message)
    assert payload["status"] == 200
    assert payload["method"] == "GET"
    assert payload["path"].startswith("/logged")
    assert payload["route"] == "/logged"
    assert payload["duration_ms"] >= 0
    assert payload["latency_ms"] == payload["duration_ms"]
    assert payload["request_id"] == "abc123"


def test_span_closure_and_error_tagging() -> None:
    app = ForziumApp()

    @app.get("/ok")
    def ok_route() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/boom")
    def boom_route() -> None:
        raise RuntimeError("boom")

    client = TestClient(app)

    # Ensure clean state for span tracking
    manual_spans = getattr(monitoring, "_manual_spans", None)
    span_lookup = getattr(monitoring, "_manual_span_lookup", None)
    if manual_spans is not None:
        manual_spans.clear()
    if span_lookup is not None:
        span_lookup.clear()

    ok_response = client.get("/ok")
    assert ok_response.status_code == 200
    assert monitoring.get_current_span_id() is None

    boom_response = client.get("/boom")
    assert boom_response.status_code == 500
    assert monitoring.get_current_span_id() is None

    spans = [
        span
        for span in monitoring.get_traces()
        if getattr(span, "name", "").startswith("/")
    ]
    assert any(getattr(span, "closed", False) for span in spans)
    ok_span = next(span for span in spans if getattr(span, "name", "") == "/ok")
    boom_span = next(span for span in spans if getattr(span, "name", "") == "/boom")
    assert ok_span.closed is True
    assert boom_span.closed is True
    assert ok_span.attributes.get("http.status_code") == 200
    assert ok_span.attributes.get("forzium.error") is False
    assert boom_span.attributes.get("http.status_code") == 500
    assert boom_span.attributes.get("forzium.error") is True