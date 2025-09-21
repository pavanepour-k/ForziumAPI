import asyncio
import json

from forzium.app import ForziumApp


def test_otlp_exporter_persists_on_failure(tmp_path, monkeypatch):
    fail_dir = tmp_path / "fail"
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:9")
    monkeypatch.setenv("FORZIUM_OTLP_FAIL_DIR", str(fail_dir))
    import importlib
    import infrastructure.monitoring as monitoring
    importlib.reload(monitoring)

    app = ForziumApp()
    monitoring.register_observability_persistence(app, str(tmp_path / "obs.db"))

    with monitoring.start_span("span"):
        pass
    monitoring.record_metric("m", 1)
    asyncio.run(app.startup())
    asyncio.run(app.shutdown())
    files = list(fail_dir.glob("*.json"))
    assert files, "failed batches should be persisted"
    data = json.loads(files[0].read_text())
    assert any(item.get("name") == "m" for item in data) or any(
        item.get("spans") for item in data
    )