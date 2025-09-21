"""Tests for distributed background task queue integration."""

from __future__ import annotations

import asyncio

from forzium.app import ForziumApp
from forzium.dependency import BackgroundTasks
from forzium.http import Response
from forzium.task_queue import RedisTaskQueue


class DummyRedis:
    def __init__(self) -> None:
        self.items: list[str] = []

    def lpush(self, _name: str, value: str) -> None:
        self.items.insert(0, value)

    def brpop(self, _name: str, timeout: int = 0):
        if not self.items:
            return None
        return ("queue", self.items.pop().encode())


_hits: list[int] = []


def _record(value: int) -> None:
    _hits.append(value)


def test_background_tasks_enqueue_to_queue() -> None:
    global _hits
    _hits = []
    queue = RedisTaskQueue(client=DummyRedis())
    tasks = BackgroundTasks(queue=queue)
    tasks.add_task(_record, 1)
    asyncio.run(tasks())
    assert _hits == []
    func, args, kwargs = queue.pop()  # type: ignore[misc]
    func(*args, **kwargs)
    assert _hits == [1]


def test_app_queues_background_tasks() -> None:
    global _hits
    _hits = []
    queue = RedisTaskQueue(client=DummyRedis())
    app = ForziumApp(task_queue=queue)

    @app.get("/")
    def handler(background: BackgroundTasks) -> Response:
        background.add_task(_record, 2)
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
    assert _hits == []
    func, args, kwargs = queue.pop()  # type: ignore[misc]
    func(*args, **kwargs)
    assert _hits == [2]