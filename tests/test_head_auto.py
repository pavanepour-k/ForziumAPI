from forzium.app import ForziumApp
from forzium.testclient import TestClient


def test_head_falls_back_to_get() -> None:
    app = ForziumApp()

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"msg": "ok"}

    client = TestClient(app)
    get_resp = client.get("/ping")
    head_resp = client.head("/ping")
    assert head_resp.status_code == 200
    assert head_resp.text == ""
    assert head_resp.headers == get_resp.headers
    methods = {r["method"] for r in app.routes if r["path"] == "/ping"}
    assert methods == {"GET", "HEAD"}