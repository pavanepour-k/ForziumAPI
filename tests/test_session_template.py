"""Session middleware and template renderer integration tests."""

import json
import tempfile
from pathlib import Path

from forzium import ForziumApp, TemplateRenderer, TestClient
from forzium.middleware import SessionMiddleware


def test_session_middleware_roundtrip() -> None:
    app = ForziumApp()
    app.add_middleware(SessionMiddleware, secret="k")

    @app.get("/visit")
    def visit(session):
        count = session.get("count", 0) + 1
        session["count"] = count
        return {"count": count}

    client = TestClient(app)
    resp1 = client.get("/visit")
    cookie = resp1.headers.get("set-cookie", "session=")
    value = cookie.split("=", 1)[1]
    resp2 = client.get("/visit", params={"session": value})
    assert resp1.json() == {"count": 1}
    assert resp2.json() == {"count": 2}


def test_session_middleware_with_path_param_alignment() -> None:
    app = ForziumApp()
    app.add_middleware(SessionMiddleware, secret="secret")

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

    status, body_text, headers = handler(b"", ("7",), b"")
    assert status == 200
    assert json.loads(body_text) == {"session_last": 7, "item_id": 7}
    assert observed[0] == (dict, int)

    cookie = headers.get("set-cookie", "session=")
    value = cookie.split("=", 1)[1]
    status2, body_text2, headers2 = handler(
        b"", ("8",), f"session={value}".encode()
    )
    assert status2 == 200
    assert json.loads(body_text2) == {"session_last": 8, "item_id": 8}
    assert observed[-1] == (dict, int)
    assert "set-cookie" in headers2


def test_template_renderer() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "greet.txt"
        path.write_text("hi {name}")
        renderer = TemplateRenderer(tmp)
        assert renderer.render("greet.txt", name="bob") == "hi bob"
