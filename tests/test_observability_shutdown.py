from infrastructure.monitoring import (
    record_metric,
    register_observability_persistence,
    start_span,
)
from forzium.app import ForziumApp


def test_persist_on_shutdown(tmp_path):
    db = tmp_path / "obs.db"
    app = ForziumApp()
    register_observability_persistence(app, str(db))
    record_metric("requests", 1)
    with start_span("work"):
        pass
    import asyncio

    asyncio.run(app.startup())
    asyncio.run(app.shutdown())
    import sqlite3

    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("SELECT value FROM metrics WHERE name='requests'")
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT COUNT(*) FROM traces")
    assert cur.fetchone()[0] >= 1
    conn.close()