"""Verify persistence of latency histograms and traces."""

import sqlite3

from infrastructure.monitoring import (
    get_traces,
    persist_observability,
    query_metric,
    record_latency,
    record_metric,
    start_span,
)


def test_persist_observability(tmp_path) -> None:
    record_latency("/endpoint", 5.0)
    record_metric("requests", 1)
    with start_span("test"):  # generate a trace
        pass
    db = tmp_path / "obs.db"
    persist_observability(str(db))
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM latencies")
    assert cur.fetchone()[0] >= 1
    cur.execute("SELECT value FROM metrics WHERE name='requests'")
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT COUNT(*) FROM traces")
    assert cur.fetchone()[0] == len(list(get_traces()))
    conn.close()
    assert query_metric(str(db), "requests") == 1
