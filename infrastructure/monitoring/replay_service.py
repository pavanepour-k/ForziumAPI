"""Background OTLP replay service recording failure metrics."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import os
from typing import TYPE_CHECKING

from . import record_metric
from .otlp_exporter import OTLPBatchExporter

if TYPE_CHECKING:  # pragma: no cover
    from forzium.app import ForziumApp


def start_replay_service(
    directory: str, endpoint: str, interval: float = 60.0
) -> threading.Thread:
    """Start a daemon thread replaying failed OTLP batches.

    The metric ``otlp_replay_failures`` reflects remaining batch count after
    each replay attempt.
    """

    exporter = OTLPBatchExporter(endpoint, fail_dir=directory)

    def _worker() -> None:
        while True:
            pending = len(list(Path(directory).glob("*.json")))
            processed = exporter.replay_failed()
            remaining = pending - processed
            record_metric("otlp_replay_failures", float(remaining))
            time.sleep(interval)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return thread


def register_replay_service(
    app: "ForziumApp", directory: str, endpoint: str, interval: float | None = None
) -> None:
    """Start OTLP replay service when *app* starts."""

    inter = (
        interval
        if interval is not None
        else float(os.getenv("FORZIUM_REPLAY_INTERVAL", "60"))
    )

    def _start() -> None:
        start_replay_service(directory, endpoint, inter)

    app.on_event("startup")(_start)


__all__ = ["start_replay_service", "register_replay_service"]
