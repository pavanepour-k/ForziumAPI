"""OTLP exporter tests."""

from urllib import error, request

from infrastructure.monitoring.otlp_exporter import OTLPBatchExporter


def test_otlp_exporter_retry(monkeypatch) -> None:
    exporter = OTLPBatchExporter("http://example")
    exporter.add({"m": 1})

    calls = {"n": 0}

    def fake_urlopen(req, timeout=1):  # pragma: no cover - network stub
        calls["n"] += 1
        if calls["n"] < 2:
            raise error.URLError("down")
        return object()

    monkeypatch.setattr(request, "urlopen", fake_urlopen)
    assert exporter.flush() is True
    assert calls["n"] == 2
    assert exporter.buffer == []


def test_otlp_exporter_failure(monkeypatch) -> None:
    exporter = OTLPBatchExporter("http://example", max_retries=2)
    exporter.add({"m": 1})

    def fail(req, timeout=1):  # pragma: no cover - network stub
        raise error.URLError("down")

    monkeypatch.setattr(request, "urlopen", fail)
    assert exporter.flush() is False
    assert exporter.buffer
