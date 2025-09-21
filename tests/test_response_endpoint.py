import time

from forzium import ForziumApp
from forzium.http import BackgroundTask, Response


def _get_handler(app: ForziumApp, path: str = "/"):
    route = next(r for r in app.routes if r["path"] == path)
    return app._make_handler(
        route["func"],
        route["param_names"],
        route["param_converters"],
        route["query_params"],
        route["expects_body"],
        route["dependencies"],
        route["expects_request"],
        route["method"],
        route["path"],
        route["background_param"],
    )


def test_endpoint_returns_response_with_headers():
    app = ForziumApp()

    content = b'{"msg": "ok"}'

    @app.get("/")
    def handler() -> Response:
        return Response(
            content,
            status_code=201,
            headers={"X-Test": "1"},
            media_type="application/json",
        )

    handler_fn = _get_handler(app)
    status, body, headers = handler_fn(b"", tuple(), b"")
    assert status == 201
    assert isinstance(body, bytes)
    assert body == content
    assert headers["x-test"] == "1"
    assert headers["content-type"] == "application/json"


def test_response_background_task_runs(tmp_path):
    app = ForziumApp()
    hit_file = tmp_path / "hit.txt"

    def write_file() -> None:
        hit_file.write_text("done")

    @app.get("/bg")
    def handler() -> Response:
        return Response("ok", background=BackgroundTask(write_file))

    handler_fn = _get_handler(app, "/bg")
    status, body, headers = handler_fn(b"", tuple(), b"")
    assert status == 200
    assert isinstance(body, bytes)
    assert body == b"ok"
    assert hit_file.exists() is False
    time.sleep(0.05)
    assert hit_file.read_text() == "done"


def test_response_preserves_binary_payload() -> None:
    app = ForziumApp()

    payload = bytes(range(256))

    @app.get("/binary")
    def handler() -> Response:
        return Response(
            payload,
            media_type="application/octet-stream",
            headers={"X-Bin": "yes"},
        )

    handler_fn = _get_handler(app, "/binary")
    status, body, headers = handler_fn(b"", tuple(), b"")
    assert status == 200
    assert isinstance(body, bytes)
    assert body == payload
    assert headers["content-type"] == "application/octet-stream"
    assert headers["x-bin"] == "yes"