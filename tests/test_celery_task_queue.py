"""Ensure Celery task queue enqueues tasks correctly."""

from forzium.task_queue import CeleryTaskQueue


class DummyCelery:
    def __init__(self) -> None:
        self.sent: list[tuple[str, tuple, dict]] = []

    def send_task(
        self,
        name: str,
        args: tuple | None = None,
        kwargs: dict | None = None,
    ) -> None:
        self.sent.append((name, args or tuple(), kwargs or {}))


def sample(a: int, b: int) -> int:
    return a + b


def test_enqueue_calls_send_task() -> None:
    celery = DummyCelery()
    queue = CeleryTaskQueue(celery)
    queue.enqueue(sample, 1, 2)
    assert celery.sent == [
        ("tests.test_celery_task_queue.sample", (1, 2), {})
    ]