"""Validate library mode parity with server mode dispatch."""

import socket
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any

import pytest

from forzium import ForziumApp
from forzium.http import BackgroundTasks, Depends, Request
from forzium.responses import JSONResponse
from forzium.testclient import TestClient
from forzium_engine import ForziumHttpServer
from tests.http_client import post
from tests.normalization import normalize_response


pytest.importorskip("forzium_engine")


def _allocate_port() -> int:
    """Return an available localhost TCP port."""

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port
def test_library_and_server_mode_responses_match() -> None:
    """Successful requests should yield the same payload and metadata."""

    port = _allocate_port()
    server = ForziumHttpServer()
    app = ForziumApp(server)
    client = TestClient(app)

    background_records: list[dict[str, Any]] = []

    @dataclass
    class ItemPayload:
        name: str
        quantity: int

    def read_token(request: Request) -> str:
        return request.headers.get("x-token", "missing")

    @app.post("/items")
    def create_item(
        payload: ItemPayload,
        background: BackgroundTasks,
        verbose: bool = False,
        token: str = Depends(read_token),
    ) -> JSONResponse:
        record = {
            "sent": False,
            "event": threading.Event(),
            "violations": [],
        }
        background_records.append(record)

        def run_task(rec: dict[str, Any] = record) -> None:
            if not rec["sent"]:
                rec["violations"].append("executed before response")
            rec["event"].set()

        background.add_task(run_task)

        payload_dict = asdict(payload)
        payload_dict["verbose"] = verbose
        payload_dict["token"] = token
        return JSONResponse(
            payload_dict,
            headers={"x-mode": "handled"},
            background=background,
        )

    server.serve(f"127.0.0.1:{port}")
    time.sleep(0.2)
    try:
        payload = {"name": "Widget", "quantity": 3}
        query = {"verbose": "true"}
        headers = {"X-Token": "abc123"}

        lib_index = len(background_records)
        library_response = client.post(
            "/items",
            json_body=payload,
            params=query,
            headers={k.lower(): v for k, v in headers.items()},
        )
        assert len(background_records) == lib_index + 1
        lib_record = background_records[lib_index]
        lib_record["sent"] = True
        assert lib_record["event"].wait(0.5)
        assert lib_record["violations"] == []

        server_index = len(background_records)
        server_response = post(
            f"http://127.0.0.1:{port}/items",
            payload,
            params=query,
            headers=headers,
        )
        assert len(background_records) == server_index + 1
        srv_record = background_records[server_index]
        srv_record["sent"] = True
        assert srv_record["event"].wait(0.5)
        assert srv_record["violations"] == []

        assert normalize_response(library_response) == normalize_response(
            server_response
        )
    finally:
        server.shutdown()


def test_library_and_server_mode_validation_match() -> None:
    """Validation errors should align across dispatch modes."""

    port = _allocate_port()
    server = ForziumHttpServer()
    app = ForziumApp(server)
    client = TestClient(app)

    @dataclass
    class ItemPayload:
        name: str
        quantity: int

    @app.post("/items")
    def create_item(payload: ItemPayload) -> JSONResponse:
        return JSONResponse(asdict(payload))

    server.serve(f"127.0.0.1:{port}")
    time.sleep(0.2)
    try:
        invalid_payload = {"name": "Widget"}

        lib_response = client.post("/items", json_body=invalid_payload)
        srv_response = post(
            f"http://127.0.0.1:{port}/items",
            invalid_payload,
        )
        assert normalize_response(lib_response) == normalize_response(srv_response)
    finally:
        server.shutdown()