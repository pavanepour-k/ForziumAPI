from forzium import ForziumApp, TestClient


def create_app() -> ForziumApp:
    app = ForziumApp()

    @app.get("/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/echo")
    def echo(payload: dict) -> dict:
        return payload

    return app


def test_get_request() -> None:
    app = create_app()
    client = TestClient(app)
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_post_request() -> None:
    app = create_app()
    client = TestClient(app)
    resp = client.post("/echo", json_body={"a": 1})
    assert resp.status_code == 200
    assert resp.json() == {"a": 1}
