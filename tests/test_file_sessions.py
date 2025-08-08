"""Verify file-backed session persistence."""

import tempfile
from pathlib import Path

from forzium import ForziumApp, TestClient
from forzium.middleware import FileSessionMiddleware


def test_file_session_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "sessions.json"
        app = ForziumApp()
        app.add_middleware(FileSessionMiddleware, path=str(path))

        @app.get("/visit")
        def visit(session):
            count = session.get("count", 0) + 1
            session["count"] = count
            return {"count": count}

        client = TestClient(app)
        resp1 = client.get("/visit")
        cookie = resp1.headers.get("set-cookie", "session_id=")
        sid = cookie.split("=", 1)[1]
        resp2 = client.get("/visit", params={"session_id": sid})
        assert resp2.json() == {"count": 2}
