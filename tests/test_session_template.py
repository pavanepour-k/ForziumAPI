"""Session middleware and template renderer integration tests."""

import tempfile
from pathlib import Path

from forzium import ForziumApp, TestClient, TemplateRenderer
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


def test_template_renderer() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "greet.txt"
        path.write_text("hi {name}")
        renderer = TemplateRenderer(tmp)
        assert renderer.render("greet.txt", name="bob") == "hi bob"
