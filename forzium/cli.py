"""Developer tooling for Forzium."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import pkgutil
import subprocess  # nosec B404
import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from importlib import import_module
from importlib.metadata import entry_points
from pathlib import Path
from types import ModuleType
from typing import Any
from datetime import datetime, timezone
from textwrap import dedent


LOGGER = logging.getLogger("forzium.cli")

def _run(cmd: list[str]) -> None:
    if os.getenv("FORZIUM_DRYRUN"):
        print(" ".join(cmd))
    else:
        subprocess.run(cmd, check=True)  # nosec B603



@dataclass(slots=True)
class LoadedApp:
    """Container for the resolved Forzium application."""

    module: ModuleType
    app: Any
    server: Any
    module_name: str
    app_name: str


def _parse_app_path(path: str) -> tuple[str, str]:
    module_name, _, attr = path.partition(":")
    return module_name, attr or "app"


def _determine_default_app_path() -> tuple[str, str]:
    env_target = os.getenv("FORZIUM_APP")
    if env_target:
        return _parse_app_path(env_target)

    if (Path.cwd() / "main.py").exists():
        return "main", "app"
    if (Path.cwd() / "app.py").exists():
        return "app", "app"
    if (Path.cwd() / "core" / "__init__.py").exists():
        return "core", "app"
    raise RuntimeError(
        "Unable to locate a Forzium application. Provide --app or set FORZIUM_APP"
    )


def _load_app(path: str | None) -> LoadedApp:
    module_name: str
    attr_name: str
    if path:
        module_name, attr_name = _parse_app_path(path)
    else:
        module_name, attr_name = _determine_default_app_path()

    module = import_module(module_name)
    if not hasattr(module, attr_name):
        raise RuntimeError(f"Module '{module_name}' does not define '{attr_name}'")
    app = getattr(module, attr_name)
    server = getattr(module, "server", None)
    if server is None:
        server = getattr(app, "server", None)
    if server is None:
        raise RuntimeError(
            "Resolved application is not bound to a Forzium server. "
            "Instantiate ForziumApp with a ForziumHttpServer and expose either "
            "'server' on the module or set app.server."
        )
    return LoadedApp(module=module, app=app, server=server, module_name=module_name, app_name=attr_name)


def _run_coroutine(coro: Any) -> None:
    if not asyncio.iscoroutine(coro):
        return
    try:
        asyncio.run(coro)
    except RuntimeError as exc:  # pragma: no cover - defensive fallback
        if "asyncio.run() cannot be called" not in str(exc):
            raise
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(coro)
        finally:
            loop.close()


def _start_server(loaded: LoadedApp, host: str, port: int, *, block: bool) -> None:
    address = f"{host}:{port}"
    _run_coroutine(getattr(loaded.app, "startup", lambda: None)())
    loaded.server.serve(address)  # type: ignore[attr-defined]
    print(
        f"Forzium application '{loaded.module_name}:{loaded.app_name}' running on http://{address}"
    )
    if not block:
        return
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        LOGGER.info("Server stopped.")
    finally:
        with suppress(Exception):
            loaded.server.shutdown()
        _run_coroutine(getattr(loaded.app, "shutdown", lambda: None)())


def scaffold(path: str) -> None:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    project_name = target.name or "forzium-app"
    script_name = project_name.replace("-", "_") or "forzium_app"
    (target / "app.py").write_text(
        "from forzium import ForziumApp\n"
        "from forzium_engine import ForziumHttpServer\n\n"
        "server = ForziumHttpServer()\n"
        "app = ForziumApp(server)\n\n"
        "@app.get(\"/health\")\n"
        "def health() -> dict[str, str]:\n"
        "    return {\"status\": \"ok\"}\n"
    )
    (target / "main.py").write_text(
        "\"\"\"Sample Forzium application entry point.\"\"\"\n\n"
        "from __future__ import annotations\n\n"
        "from app import app, server\n\n"
        "def run(host: str = \"127.0.0.1\", port: int = 8000) -> None:\n"
        "    \"\"\"Start the bundled Forzium server.\"\"\"\n"
        "    address = f\"{host}:{port}\"\n"
        "    server.serve(address)  # type: ignore[attr-defined]\n"
        "    print(f\"Forzium app available at http://{address}\")\n"
        "    try:\n"
        "        import time\n\n"
        "        while True:\n"
        "            time.sleep(1)\n"
        "    except KeyboardInterrupt:\n"
        "        server.shutdown()\n\n"
        "if __name__ == \"__main__\":\n"
        "    run()\n"
    )
    (target / "Dockerfile").write_text(
        "FROM python:3.12-slim\n"
        "WORKDIR /app\n"
        "COPY requirements.txt ./\n"
        "RUN pip install --no-cache-dir -r requirements.txt\n"
        "COPY . .\n"
        "CMD [\"python\", \"-m\", \"forzium.cli\", \"run\", \"--app\", \"main:app\"]\n"
    )
    (target / "requirements.txt").write_text(
        "forzium==0.1.4\nforzium-engine==0.1.4\n"
    )
    (target / "README.md").write_text(
        dedent(
            """
            # Forzium Starter Application

            This project was generated by `forzium new` and provides a minimal
            Forzium application ready for local development or containerized deployment.
            Install the dependencies listed in `requirements.txt` or build a wheel via
            `python -m build`.
            """
        ).strip()
        + "\n"
    )
    (target / "pyproject.toml").write_text(
        dedent(
            f"""
            [build-system]
            requires = ["setuptools>=69.0", "wheel"]
            build-backend = "setuptools.build_meta"

            [project]
            name = "{project_name}"
            version = "0.1.0"
            description = "Forzium starter application."
            readme = "README.md"
            requires-python = ">=3.10"
            dependencies = [
                "forzium==0.1.4",
                "forzium-engine==0.1.4",
            ]

            [project.scripts]
            {script_name} = "main:run"

            [tool.setuptools]
            py-modules = ["app", "main"]
            """
        ).strip()
        + "\n"
    )
    root = Path(__file__).resolve().parents[1]
    config = root / ".pre-commit-config.yaml"
    if config.exists():
        (target / ".pre-commit-config.yaml").write_text(config.read_text())


def scaffold_plugin(path: str, name: str) -> None:
    target = Path(path)
    pkg = target / name
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text(
        "def register(subparsers) -> None:\n"
        f"    parser = subparsers.add_parser('{name}')\n"
        f"    parser.set_defaults(func=lambda a: print('{name} plugin'))\n"
    )
    (target / "pyproject.toml").write_text(
        "[project]\n"
        f'name = "{name}"\n'
        'version = "0.1.4"\n'
        '[project.entry-points."forzium.plugins"]\n'
        f"{name} = '{name}:register'\n"  # noqa: E231
    )


def _cmd_bench(args: argparse.Namespace) -> None:
    """Run tensor benchmarks, emit JSON, and persist a report file."""

    from core.service import gpu

    size = args.size
    a = [[float(i + j) for j in range(size)] for i in range(size)]
    b = [[float((i * j) % 5) for j in range(size)] for i in range(size)]
    k = min(3, size)
    kernel = [[1.0] * k for _ in range(k)]
    metrics = gpu.benchmark_tensor_ops(a, b, kernel)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "size": size,
        "metrics": metrics,
    }
    formatted = json.dumps(report, indent=2)
    sys.stdout.write(formatted + "\n")
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(formatted + "\n")
    print(f"Benchmark results written to {output_path}", file=sys.stderr)


def _load_plugins(
    sub: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    plugins_pkg: ModuleType | None
    try:
        import forzium.plugins as plugins_module

        plugins_pkg = plugins_module
    except Exception:
        plugins_pkg = None
    if plugins_pkg:
        for _, name, _ in pkgutil.iter_modules(plugins_pkg.__path__):
            module = import_module(f"forzium.plugins.{name}")
            if hasattr(module, "register"):
                module.register(sub)
    for ep in entry_points().select(group="forzium.plugins"):
        module = ep.load()
        if hasattr(module, "register"):
            module.register(sub)


def _resolve_host_port(args: argparse.Namespace) -> tuple[str, int]:
    host = (
        args.host
        or os.getenv("FORZIUM_HOST")
        or os.getenv("HOST")
        or "127.0.0.1"
    )
    raw_port: Any = args.port
    if raw_port is None:
        raw_port = os.getenv("FORZIUM_PORT") or os.getenv("PORT") or "8000"
    try:
        port = int(raw_port)
    except (TypeError, ValueError) as exc:  # noqa: TRY003
        raise RuntimeError("Port must be an integer value") from exc
    return host, port


def _cmd_run(args: argparse.Namespace) -> None:
    host, port = _resolve_host_port(args)
    loaded = _load_app(getattr(args, "app_path", None))
    _start_server(loaded, host, port, block=not getattr(args, "no_block", False))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="forzium")
    sub = parser.add_subparsers(dest="cmd")

    new = sub.add_parser("new")
    new.add_argument("path")
    sub.add_parser("build")
    sub.add_parser("test")
    sub.add_parser("lint")
    bench = sub.add_parser("bench")
    bench.add_argument("--size", type=int, default=64)
    bench.add_argument(
        "--output",
        default="bench-results.json",
        help="Path to write the benchmark results JSON report (default: bench-results.json)",
    )
    bench.set_defaults(func=_cmd_bench)
    plugin = sub.add_parser("plugin")
    plugin.add_argument("path")
    plugin.add_argument("name")
    run_parser = sub.add_parser("run")
    run_parser.add_argument(
        "--host",
        help="Host interface to bind (default: FORZIUM_HOST/HOST or 127.0.0.1)",
    )
    run_parser.add_argument(
        "--port",
        type=int,
        help="Port to bind (default: FORZIUM_PORT/PORT or 8000)",
    )
    run_parser.add_argument(
        "--app",
        dest="app_path",
        help="Python path to the Forzium app, e.g. 'main:app'",
    )
    run_parser.add_argument(
        "--no-block",
        action="store_true",
        help="Start the server without blocking (useful for testing)",
    )
    run_parser.set_defaults(func=_cmd_run)
    replay = sub.add_parser("replay-otlp")
    replay.add_argument("directory")
    replay.add_argument("endpoint")
    _load_plugins(sub)

    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        args.func(args)
    elif args.cmd == "new":
        scaffold(args.path)
    elif args.cmd == "build":
        _run(["python", "build_pipeline.py"])
    elif args.cmd == "test":
        _run(["pytest", "-q"])
    elif args.cmd == "lint":
        _run(["ruff", "."])
    elif args.cmd == "plugin":
        scaffold_plugin(args.path, args.name)
    elif args.cmd == "replay-otlp":
        from infrastructure.monitoring.otlp_exporter import OTLPBatchExporter

        exporter = OTLPBatchExporter(args.endpoint, fail_dir=args.directory)
        exporter.replay_failed()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
