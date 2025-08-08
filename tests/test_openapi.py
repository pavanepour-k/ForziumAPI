"""Tests for automatic OpenAPI schema generation."""

from dataclasses import dataclass

from forzium import ForziumApp


def test_openapi_generation() -> None:
    app = ForziumApp()
    app.add_security_scheme(
        "ApiKeyAuth", {"type": "apiKey", "name": "X-API-Key", "in": "header"}
    )

    router = ForziumApp()

    @dataclass
    class Item:
        id: int

    @router.get("/items", tags=["items"])
    def list_items() -> list[Item]:
        return [Item(1)]

    app.include_router(router, prefix="/v1")

    schema = app.openapi_schema()
    item_schema = schema["components"]["schemas"]["Item"]
    assert item_schema["properties"]["id"]["type"] == "integer"
    assert "ApiKeyAuth" in schema["components"]["securitySchemes"]
    op = schema["paths"]["/v1/items"]["get"]
    assert op["tags"] == ["items"]
    assert op["responses"]["200"]["content"]["application/json"]["schema"] == {
        "type": "array",
        "items": {"$ref": "#/components/schemas/Item"},
    }
    handler = next(r["func"] for r in app.routes if r["path"] == "/openapi.json")
    assert handler() == schema


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
