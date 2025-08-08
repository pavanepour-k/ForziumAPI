import asyncio
import time

import infrastructure.monitoring.otlp_exporter as exporter
from forzium.app import ForziumApp
from infrastructure.monitoring import get_metric
from infrastructure.monitoring.replay_service import register_replay_service


def test_replay_service_records_failures(tmp_path, monkeypatch) -> None:
    fail_dir = tmp_path / "buf"
    fail_dir.mkdir()
    (fail_dir / "1.json").write_text("[]")

    monkeypatch.setattr(exporter.OTLPBatchExporter, "flush", lambda self: False)
    app = ForziumApp()
    register_replay_service(app, str(fail_dir), "http://example", interval=0.01)
    asyncio.run(app.startup())
    time.sleep(0.05)
    time.sleep(0.05)
    assert list(fail_dir.glob("*.json"))
    assert get_metric("otlp_replay_failures") >= 1.0
