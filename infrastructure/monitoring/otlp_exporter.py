"""OTLP batch exporter with retry support."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List
from urllib import error, request


class OTLPBatchExporter:
    """Buffer metrics and traces then export with retries."""

    def __init__(
        self, endpoint: str, max_retries: int = 3, fail_dir: str | None = None
    ) -> None:
        self.endpoint = endpoint
        self.max_retries = max_retries
        self.buffer: List[Dict[str, Any]] = []
        self.fail_dir = Path(fail_dir) if fail_dir else None
        if self.fail_dir:
            self.fail_dir.mkdir(parents=True, exist_ok=True)

    def add(self, item: Dict[str, Any]) -> None:
        """Append *item* to the send buffer."""

        self.buffer.append(item)

    def flush(self) -> bool:
        """Send buffered items. Return True on success."""

        if not self.buffer:
            return True
        payload = json.dumps(self.buffer).encode()
        req = request.Request(self.endpoint, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        for attempt in range(1, self.max_retries + 1):
            try:
                request.urlopen(req, timeout=1)
            except error.URLError:
                if attempt == self.max_retries:
                    if self.fail_dir:
                        ts = int(time.time() * 1000)
                        path = self.fail_dir / f"{ts}.json"
                        path.write_text(json.dumps(self.buffer))
                    return False
                time.sleep(0.1 * attempt)
            else:
                self.buffer.clear()
                return True
        return False

    def replay_failed(self) -> int:
        """Replay persisted batches. Return number of files processed."""

        if not self.fail_dir:
            return 0
        count = 0
        for file in sorted(self.fail_dir.glob("*.json")):
            data = json.loads(file.read_text())
            self.buffer.extend(data)
            if self.flush():
                file.unlink()
                count += 1
            else:  # pragma: no cover - stop on first failure
                break
        return count


__all__ = ["OTLPBatchExporter"]
