"""Tests for automatic OpenAPI schema generation."""

from dataclasses import dataclass
from typing import Any, Callable, cast

from forzium import Depends, ForziumApp


def test_openapi_generation() -> None:
    app = ForziumApp()
    app.add_security_scheme(
        "ApiKeyAuth",
        {"type": "apiKey", "name": "X-API-Key", "in": "header"},
    )

    router = ForziumApp()

    calls: list[str] = []

    def dep_a() -> None:
        calls.append("a")

    def dep_b() -> None:
        calls.append("b")

    @dataclass
    class Item:
        id: int

    @router.get(
        "/items/{item_id}",
        tags=["items"],
        responses={404: {"description": "Not Found"}},
        dependencies=[Depends(dep_a)],
    )
    def get_item(item_id: int, q: int) -> Item:
        return Item(item_id)

    app.include_router(router, prefix="/v1", dependencies=[Depends(dep_b)])
    route = next(r for r in app.routes if r["path"] == "/v1/items/{item_id}")
    handler = app._make_handler(  # type: ignore[attr-defined]
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
        [route.get("dependency_overrides", {}), app.dependency_overrides],
    )
    status, _, _ = handler(b"", ("1",), b"q=2")
    assert status == 200
    assert calls == ["a", "b"]

    schema = app.openapi_schema()
    item_schema = schema["components"]["schemas"]["Item"]
    assert item_schema["properties"]["id"]["type"] == "integer"
    assert "ApiKeyAuth" in schema["components"]["securitySchemes"]
    op = schema["paths"]["/v1/items/{item_id}"]["get"]
    assert op["tags"] == ["items"]
    assert any(p["name"] == "item_id" and p["in"] == "path" for p in op["parameters"])
    assert any(p["name"] == "q" and p["in"] == "query" for p in op["parameters"])
    assert "404" in op["responses"]
    schema_handler = cast(
        Callable[[], dict[str, Any]],
        next(r["func"] for r in app.routes if r["path"] == "/openapi.json"),
    )
    assert schema_handler() == schema


def test_router_tags_and_prefixes() -> None:
    """Router-level tags should merge with include tags."""

    router = ForziumApp()

    @router.get("/ping", tags=["core"])
    def ping() -> dict[str, str]:
        return {"msg": "ok"}

    app = ForziumApp()
    app.include_router(router, prefix="/api", tags=["v1"])

    schema = app.openapi_schema()
    op = schema["paths"]["/api/ping"]["get"]
    assert op["tags"] == ["core", "v1"]
    assert {"name": "core"} in schema["tags"]
    assert {"name": "v1"} in schema["tags"]


def test_openapi_summary_description() -> None:
    """Routes should expose summary and description in schema."""

    app = ForziumApp()

    @app.get("/items", summary="List items", description="Retrieve all items")
    def list_items() -> dict[str, str]:
        return {"msg": "ok"}

    schema = app.openapi_schema()
    op = schema["paths"]["/items"]["get"]
    assert op["summary"] == "List items"
    assert op["description"] == "Retrieve all items"


def test_openapi_customizer() -> None:
    """Custom OpenAPI modifications should be applied."""

    app = ForziumApp()

    @app.get("/ping")
    def ping2() -> dict[str, str]:
        return {"msg": "ok"}

    def tweak(schema: dict[str, Any]) -> dict[str, Any]:
        schema["info"] = {"title": "Forzium", "version": "1.0"}
        return schema

    app.customize_openapi(tweak)
    schema = app.openapi_schema()
    assert schema["info"]["title"] == "Forzium"