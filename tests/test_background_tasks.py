"""Tests for background task execution."""

from __future__ import annotations

import asyncio
import logging
import time

import pytest

from forzium.app import ForziumApp
from forzium.http import BackgroundTask, BackgroundTasks, Response


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


def test_background_tasks_multiple_and_errors(caplog: pytest.LogCaptureFixture) -> None:
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
    tasks.add_task(hits.append, 4)
    with caplog.at_level(logging.ERROR, logger="forzium"):
        asyncio.run(tasks())
    assert hits == [1, 2, 3, 4]
    error_logs = [
        record
        for record in caplog.records
        if record.levelno == logging.ERROR and "Background task" in record.getMessage()
    ]
    assert error_logs, "Background task failure should be logged"
    assert all(record.exc_info for record in error_logs)


async def _async_raise() -> None:
    raise RuntimeError("boom")


def test_async_background_task_logs_error(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR, logger="forzium")
    task = BackgroundTask(_async_raise)
    with pytest.raises(RuntimeError):
        asyncio.run(task())
    messages = [record.getMessage() for record in caplog.records]
    assert any("Background task" in msg for msg in messages)
    assert all(record.exc_info for record in caplog.records if "Background task" in record.getMessage())


def test_response_run_background_logs_error(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR, logger="forzium")
    response = Response("ok", background=BackgroundTask(_async_raise))
    asyncio.run(response.run_background())
    messages = [record.getMessage() for record in caplog.records]
    assert any("Background task" in msg for msg in messages)
    assert any("Background execution" in msg for msg in messages)
    assert all(
        record.exc_info for record in caplog.records if record.name == "forzium"
    )
