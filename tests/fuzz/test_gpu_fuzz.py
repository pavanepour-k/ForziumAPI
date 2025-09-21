# noqa: E402
"""Fuzz harness for GPU elementwise addition using Atheris."""

import json
import sys

import pytest

from core.service.gpu import elementwise_add

atheris = pytest.importorskip("atheris")


def _fuzz_one_input(data: bytes) -> None:
    """Feed fuzzed data into elementwise_add."""
    try:
        payload = json.loads(data.decode("utf-8"))
    except Exception:
        return
    if not isinstance(payload, list) or len(payload) != 2:
        return
    a, b = payload
    if not (isinstance(a, list) and isinstance(b, list)):
        return
    try:
        elementwise_add(a, b)
    except Exception:
        pass


def main() -> None:
    atheris.Setup(sys.argv, _fuzz_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()