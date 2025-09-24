"""Tests for CLI run command and project scaffolding."""

from __future__ import annotations

import asyncio
import sys
import time
from importlib import import_module
from types import ModuleType

import pytest

pytest.importorskip("forzium_engine")

from forzium.cli import LoadedApp, _start_server, main as cli_main
from tests.http_client import get


def _shutdown_loaded_app(module_name: str) -> None:
    module = import_module(module_name)
    app = getattr(module, "app", None)
    server = getattr(module, "server", None)
    if server is None and app is not None:
        server = getattr(app, "server", None)
    if server is None:
        raise RuntimeError(f"Module '{module_name}' does not expose a Forzium server")
    server.shutdown()
    if app is not None and hasattr(app, "shutdown"):
        asyncio.run(app.shutdown())


def test_start_server_keyboard_interrupt(monkeypatch, caplog) -> None:
    class DummyServer:
        def __init__(self) -> None:
            self.addresses: list[str] = []
            self.shutdown_called = False

        def serve(self, address: str) -> None:
            self.addresses.append(address)

        def shutdown(self) -> None:
            self.shutdown_called = True

    class DummyApp:
        def __init__(self) -> None:
            self.startup_called = False
            self.shutdown_called = False

        async def startup(self) -> None:
            self.startup_called = True

        async def shutdown(self) -> None:
            self.shutdown_called = True

    server = DummyServer()
    app = DummyApp()
    module = ModuleType("dummy_module")
    loaded = LoadedApp(
        module=module,
        app=app,
        server=server,
        module_name=module.__name__,
        app_name="app",
    )

    def raise_interrupt(_: float) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(time, "sleep", raise_interrupt)

    caplog.set_level("INFO", logger="forzium.cli")

    _start_server(loaded, "127.0.0.1", 9000, block=True)

    assert "Server stopped." in caplog.text
    assert server.addresses == ["127.0.0.1:9000"]
    assert server.shutdown_called is True
    assert app.startup_called is True
    assert app.shutdown_called is True


def test_cli_run_starts_server(tmp_path, monkeypatch) -> None:
    module_path = tmp_path / "project"
    module_path.mkdir()
    (module_path / "main.py").write_text(
        "from forzium import ForziumApp\n"
        "from forzium_engine import ForziumHttpServer\n\n"
        "server = ForziumHttpServer()\n"
        "app = ForziumApp(server)\n\n"
        "@app.get(\"/health\")\n"
        "def health() -> dict[str, str]:\n"
        "    return {\"status\": \"ok\"}\n"
    )
    monkeypatch.chdir(module_path)
    sys.modules.pop("main", None)
    port = 8651
    cli_main([
        "run",
        "--no-block",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--app",
        "main:app",
    ])
    time.sleep(0.3)
    resp = get(f"http://127.0.0.1:{port}/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    _shutdown_loaded_app("main")
    sys.modules.pop("main", None)


def test_scaffold_new_project_structure(tmp_path) -> None:
    target = tmp_path / "demo"
    cli_main(["new", str(target)])
    app_file = target / "app.py"
    main_file = target / "main.py"
    docker_file = target / "Dockerfile"
    reqs_file = target / "requirements.txt"
    assert app_file.exists()
    assert main_file.exists()
    assert docker_file.exists()
    assert reqs_file.exists()
    assert "ForziumApp" in app_file.read_text()
    assert "run(" in main_file.read_text()
    reqs = reqs_file.read_text()
    assert "forzium==" in reqs
    assert "forzium-engine==" in reqs


def test_generated_project_runs(tmp_path, monkeypatch) -> None:
    target = tmp_path / "demo"
    cli_main(["new", str(target)])
    monkeypatch.chdir(target)
    sys.modules.pop("main", None)
    port = 8652
    cli_main([
        "run",
        "--no-block",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ])
    time.sleep(0.3)
    resp = get(f"http://127.0.0.1:{port}/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    _shutdown_loaded_app("main")
    sys.modules.pop("main", None)