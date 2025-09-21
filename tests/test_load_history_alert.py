from infrastructure import monitoring
from scripts import load_test


def test_history_and_alert(tmp_path, monkeypatch):
    hist = tmp_path / "hist.json"
    history = load_test.record_history(100, hist)
    assert history[-1]["rps"] == 100
    history = load_test.record_history(80, hist)
    chart = load_test.render_chart(history)
    assert "#" in chart
    triggered = {}

    def fake_alert(msg):
        triggered["msg"] = msg
    monkeypatch.setattr(monitoring, "send_alert", fake_alert)
    monitoring.record_throughput(50, baseline=70)
    assert monitoring.get_metric("load_test_rps") == 50
    assert "msg" in triggered