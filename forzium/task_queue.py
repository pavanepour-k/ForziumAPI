"""Distributed task queue backends."""

from __future__ import annotations

import importlib
import json
from typing import Any, Callable


class RedisTaskQueue:
    """A minimal Redis-backed task queue."""

    def __init__(
        self,
        *,
        url: str | None = None,
        client: Any | None = None,
        queue_name: str = "forzium_tasks",
    ) -> None:
        if client is None:
            try:
                import redis  # type: ignore
            except Exception as exc:  # pragma: no cover - import guard
                raise RuntimeError("redis package required for RedisTaskQueue") from exc
            self.client = redis.Redis.from_url(url or "redis://localhost:6379/0")
        else:
            self.client = client
        self.queue_name = queue_name

    def enqueue(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        payload = json.dumps(
            {
                "func": f"{func.__module__}:{func.__name__}",
                "args": args,
                "kwargs": kwargs,
            }
        )
        self.client.lpush(self.queue_name, payload)

    def pop(
        self, *, timeout: int = 0
    ) -> tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]] | None:
        item = self.client.brpop(self.queue_name, timeout=timeout)
        if item is None:
            return None
        _, data = item
        message = json.loads(data.decode())
        module_name, func_name = message["func"].split(":")
        module = importlib.import_module(module_name)
        func = getattr(module, func_name)
        return func, tuple(message["args"]), dict(message["kwargs"])

    def worker(self, *, poll_interval: float = 0.1) -> None:
        while True:
            task = self.pop(timeout=1)
            if task is None:
                continue
            func, args, kwargs = task
            func(*args, **kwargs)


class CeleryTaskQueue:
    """Adapter around a Celery application for distributed tasks."""

    def __init__(self, app: Any) -> None:
        self.app = app

    def enqueue(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        task_name = f"{func.__module__}.{func.__name__}"
        self.app.send_task(task_name, args=args, kwargs=kwargs)