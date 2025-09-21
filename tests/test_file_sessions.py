"""Verify file-backed session persistence."""

import json
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


def test_file_session_with_path_param_alignment() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "sessions.json"
        app = ForziumApp()
        app.add_middleware(FileSessionMiddleware, path=str(path))

        observed: list[tuple[type[dict], type[int]]] = []

        @app.get("/items/{item_id:int}")
        def read_item(session, item_id: int):
            session["last"] = item_id
            observed.append((type(session), type(item_id)))
            return {"session_last": session["last"], "item_id": item_id}

        route = next(
            r for r in app.routes if r["path"] == "/items/{item_id:int}" and r["method"] == "GET"
        )
        handler = app._make_handler(  # pylint: disable=protected-access
            route["func"],
            route["param_names"],
            route["param_converters"],
            route["query_params"],
            route.get("body_param"),
            route["dependencies"],
            route.get("expects_request", False),
            route["method"],
            route["path"],
            route.get("background_param"),
        )

        status, body_text, headers = handler(b"", ("2",), b"")
        assert status == 200
        assert json.loads(body_text) == {"session_last": 2, "item_id": 2}
        assert observed[0] == (dict, int)

        sid = headers.get("set-cookie", "session_id=")
        value = sid.split("=", 1)[1]
        status2, body_text2, headers2 = handler(
            b"", ("3",), f"session_id={value}".encode()
        )
        assert status2 == 200
        assert json.loads(body_text2) == {"session_last": 3, "item_id": 3}
        assert observed[-1] == (dict, int)
        assert "set-cookie" in headers2