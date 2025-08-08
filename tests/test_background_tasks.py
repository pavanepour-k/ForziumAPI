"""Tests for background task execution."""

from __future__ import annotations

import asyncio
import time

import pytest

from forzium.app import ForziumApp
from forzium.http import BackgroundTasks, Response


def test_background_tasks_injected_and_run_after_response() -> None:
    app = ForziumApp()
    hits: list[int] = []

    @app.get("/")
    def handler(background: BackgroundTasks) -> Response:
        background.add_task(hits.append, 1)
        return Response("ok")

    route = next(r for r in app.routes if r["path"] == "/")
    handler_fn = app._make_handler(
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
    status, body, headers = handler_fn(b"", tuple(), b"")
    assert status == 200
    assert hits == []
    time.sleep(0.05)
    assert hits == [1]


def test_background_tasks_multiple_and_errors() -> None:
    hits: list[int] = []
    tasks = BackgroundTasks()
    tasks.add_task(hits.append, 1)
    tasks.add_task(hits.append, 2)
    asyncio.run(tasks())
    assert hits == [1, 2]

    tasks = BackgroundTasks()
    tasks.add_task(hits.append, 3)

    def boom() -> None:
        raise ValueError("fail")

    tasks.add_task(boom)
    with pytest.raises(ValueError):
        asyncio.run(tasks())
    assert hits == [1, 2, 3]
