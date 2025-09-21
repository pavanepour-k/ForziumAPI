"""Observability readiness gate tests."""

import json
import logging

from forzium import ForziumApp, TestClient
from infrastructure import monitoring


def test_observability_health_gate(caplog) -> None:
    monitoring.reset_observability_gate()

    app = ForziumApp(None)

    @app.get("/echo")
    def echo() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    baseline = monitoring.get_metric("requests_total")

    resp = client.get("/echo")
    assert resp.status_code == 200
    assert monitoring.get_metric("requests_total") == baseline

    caplog.set_level(logging.INFO, "forzium.observability")
    ready = client.get("/observability/ready")
    assert ready.status_code == 200
    payload = ready.json()
    assert payload["ready"] is True
    assert payload["status"] == "ready"

    records = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "forzium.observability"
        and "obs-ready" in record.message
    ]
    assert any(
        entry.get("metadata", {}).get("endpoint") == "/observability/ready"
        for entry in records
    )

    resp_after = client.get("/echo")
    assert resp_after.status_code == 200
    assert monitoring.get_metric("requests_total") == baseline + 1

    monitoring.reset_observability_gate()