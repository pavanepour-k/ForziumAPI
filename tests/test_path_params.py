# flake8: noqa
import json

from forzium import Depends, ForziumApp


def _prefix() -> str:
    return "item"


def test_path_param_and_dependency() -> None:
    app = ForziumApp()

    @app.get("/items/{item_id:int}")
    def read_item(
        item_id: int, prefix: str = Depends(_prefix)  # type: ignore[assignment]
    ) -> dict[str, str]:
        return {"name": f"{prefix}{item_id}"}

    route = app.routes[0]
    handler = app._make_handler(  # pylint: disable=protected-access
        route["func"],
        route["param_names"],
        route["param_converters"],
        route["query_params"],
        route["expects_body"],
        route["dependencies"],
        route.get("expects_request", False),
        route["method"],
        route["path"],
        route.get("background_param"),
    )

    status, body, _ = handler(b"", ("7",), b"")
    assert status == 200
    assert json.loads(body) == {"name": "item7"}