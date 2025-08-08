"""Register ForziumApp routes with the Rust server."""

import json
from typing import Callable


def register_routes(server, app) -> None:
    """Register ForziumApp routes with the Rust server."""
    for route in app.routes:
        method = route["method"]
        path = route["path"]
        func = route["func"]
        param_names = route["param_names"]
        expects_body = route["expects_body"]

        def make_handler(
            func: Callable,
            param_names: list[str],
            expects_body: bool,
        ) -> Callable[[bytes, tuple], tuple[int, str]]:
            """Create a handler converting bytes and params to a response."""

            def handler(body: bytes, params: tuple) -> tuple[int, str]:
                kwargs = {name: value for name, value in zip(param_names, params)}
                if expects_body:
                    payload = json.loads(body.decode()) if body else {}
                    kwargs["payload"] = payload
                try:
                    result = func(**kwargs)
                except ValueError as exc:
                    return 400, json.dumps({"detail": str(exc)})
                status = 200
                if (
                    isinstance(result, tuple)
                    and len(result) == 2
                    and isinstance(result[0], int)
                ):
                    status, data = result
                else:
                    data = result
                if isinstance(data, (dict, list)):
                    body_str = json.dumps(data)
                else:
                    body_str = str(data)
                return status, body_str

            return handler

        server.add_route(
            method,
            path,
            make_handler(func, param_names, expects_body),
        )
