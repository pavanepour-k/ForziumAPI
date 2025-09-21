"""Ensure Forzium responses mirror FastAPI for core validation scenarios."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Mapping

import pytest

from forzium import Depends, ForziumApp, TestClient
from forzium.responses import HTTPException
from tests.normalization import ensure_snapshot_match, normalize_response

pytest.importorskip("fastapi")
from fastapi import Depends as FastAPIDepends  # type: ignore  # noqa: E402
from fastapi import FastAPI  # type: ignore  # noqa: E402
from fastapi import HTTPException as FastAPIHTTPException  # type: ignore  # noqa: E402
from fastapi.testclient import TestClient as FastAPITestClient  # type: ignore  # noqa: E402
from pydantic import BaseModel

SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "fastapi_parity_snapshots.json"
SNAPSHOTS: Dict[str, Dict[str, Any]] = json.loads(SNAPSHOT_PATH.read_text())


class ItemModel(BaseModel):
    name: str
    qty: int


@dataclass
class MetaPayload:
    owner: str
    priority: int = 1


class TokenModel(BaseModel):
    token: str


def _build_forzium_client() -> TestClient:
    app = ForziumApp()

    @app.post("/items")
    def create_item(item: ItemModel) -> Mapping[str, Any]:
        return item.model_dump()

    @app.post("/meta")
    def create_meta(meta: MetaPayload) -> Mapping[str, Any]:
        return asdict(meta)

    @app.get("/secure")
    def secure(token: TokenModel = Depends()) -> Mapping[str, Any]:
        return {"token": token.token}

    @app.get("/boom")
    def boom() -> Mapping[str, Any]:
        raise HTTPException(status_code=418, detail="teapot")

    return TestClient(app)


def _build_fastapi_client() -> FastAPITestClient:
    app = FastAPI()

    @app.post("/items")
    def create_item(item: ItemModel) -> Mapping[str, Any]:
        return item.model_dump()

    @app.post("/meta")
    def create_meta(meta: MetaPayload) -> Mapping[str, Any]:
        return asdict(meta)

    @app.get("/secure")
    def secure(token: TokenModel = FastAPIDepends()) -> Mapping[str, Any]:
        return {"token": token.token}

    @app.get("/boom")
    def boom() -> Mapping[str, Any]:
        raise FastAPIHTTPException(status_code=418, detail="teapot")

    return FastAPITestClient(app)


@pytest.fixture(scope="module")
def parity_clients() -> tuple[TestClient, FastAPITestClient]:
    return _build_forzium_client(), _build_fastapi_client()


SCENARIOS: Dict[str, Dict[str, Any]] = {
    "item_ok": {
        "method": "POST",
        "path": "/items",
        "json": {"name": "apple", "qty": 5},
    },
    "item_invalid": {
        "method": "POST",
        "path": "/items",
        "json": {"name": "apple", "qty": "bad"},
    },
    "meta_ok": {
        "method": "POST",
        "path": "/meta",
        "json": {"owner": "alice", "priority": 2},
    },
    "meta_missing": {
        "method": "POST",
        "path": "/meta",
        "json": {"priority": 2},
    },
    "secure_missing": {
        "method": "GET",
        "path": "/secure",
    },
    "secure_ok": {
        "method": "GET",
        "path": "/secure",
        "params": {"token": "secret"},
    },
    "boom": {
        "method": "GET",
        "path": "/boom",
    },
}


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_forzium_matches_fastapi_snapshots(
    name: str, parity_clients: tuple[TestClient, FastAPITestClient]
) -> None:
    forzium_client, fastapi_client = parity_clients
    spec = SCENARIOS[name]
    method = spec["method"]
    path = spec["path"]
    json_payload = spec.get("json")
    params = spec.get("params")

    forzium_response = forzium_client.request(
        method,
        path,
        json_body=json_payload,
        params=params,
    )
    fastapi_response = fastapi_client.request(
        method,
        path,
        json=json_payload,
        params=params,
    )

    normalized_forzium = normalize_response(forzium_response)
    normalized_fastapi = normalize_response(fastapi_response)
    expected = SNAPSHOTS[name]

    ensure_snapshot_match(f"forzium__{name}", normalized_forzium, expected)
    ensure_snapshot_match(f"fastapi__{name}", normalized_fastapi, expected)
    assert normalized_forzium == normalized_fastapi