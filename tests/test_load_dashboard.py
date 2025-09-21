from scripts import load_test


def test_generate_dashboard(tmp_path):
    hist = tmp_path / "hist.json"
    load_test.record_history(100, hist)
    load_test.record_history(80, hist)
    out = tmp_path / "dash.html"
    load_test.generate_dashboard(hist, out)
    assert out.exists()
    content = out.read_text()
    assert "<html" in content
    assert "100" in content and "80" in content
    assert "-20.00" in content


def test_update_release_notes(tmp_path):
    dash = tmp_path / "dash.html"
    dash.write_text("hi", encoding="utf-8")
    notes = tmp_path / "notes.md"
    notes.write_text("# Development Updates\n", encoding="utf-8")
    load_test.update_release_notes(dash, notes)
    content = notes.read_text(encoding="utf-8")
    assert f"https://forzium.github.io/Template-maker/{dash.name}" in content