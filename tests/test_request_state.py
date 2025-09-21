from pathlib import Path

from forzium import ForziumApp, Request


def test_request_state_roundtrip(tmp_path: Path) -> None:
    app = ForziumApp()

    @app.get("/state")
    def state_endpoint(request: Request) -> str:
        request.state.user = "alice"
        return request.state.user

    route = app.routes[0]
    handler = app._make_handler(
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
    status, body, _ = handler(b"", tuple(), b"")
    assert status == 200
    assert body == "alice"