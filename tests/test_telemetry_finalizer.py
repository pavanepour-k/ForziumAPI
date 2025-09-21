from __future__ import annotations

from typing import Any

from forzium import ForziumApp, TestClient
from infrastructure import monitoring


def test_telemetry_finalizer_invoked_for_all_requests() -> None:
    app = ForziumApp()
    payloads: list[dict[str, Any]] = []

    def recorder(payload: dict[str, Any]) -> None:
        payloads.append(payload)

    monitoring.reset_telemetry_finalizer_counters()
    monitoring.register_telemetry_finalizer(recorder)
    try:
        @app.get("/ok")
        def ok_route() -> dict[str, str]:
            return {"status": "ok"}

        @app.get("/boom")
        def boom_route() -> None:
            raise RuntimeError("boom")

        client = TestClient(app)
        ok_response = client.get("/ok")
        assert ok_response.status_code == 200

        boom_response = client.get("/boom")
        assert boom_response.status_code == 500

        assert monitoring.get_telemetry_finalizer_invocations() == 2
        assert len(payloads) == 2

        by_route = {entry["route"]: entry for entry in payloads}
        assert by_route["/ok"]["status_code"] == 200
        assert by_route["/ok"]["reason"] == "normal"
        assert by_route["/ok"]["error"] is False
        assert by_route["/boom"]["status_code"] == 500
        assert by_route["/boom"]["error"] is True
        assert "duration_ms" in by_route["/ok"]
        assert "duration_ms" in by_route["/boom"]
    finally:
        monitoring.unregister_telemetry_finalizer(recorder)
        monitoring.reset_telemetry_finalizer_counters()