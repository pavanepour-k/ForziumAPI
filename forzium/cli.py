"""Developer tooling for Forzium."""

from __future__ import annotations

"""Developer command line interface for Forzium."""

import argparse
import json
import os
import subprocess
from importlib import import_module
from importlib.metadata import entry_points
from pathlib import Path
import pkgutil


def _run(cmd: list[str]) -> None:
    if os.getenv("FORZIUM_DRYRUN"):
        print(" ".join(cmd))
    else:
        subprocess.run(cmd, check=True)


def scaffold(path: str) -> None:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    (target / "app.py").write_text(
        "from forzium import ForziumApp\napp = ForziumApp()\n"
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
        'version = "0.1.0"\n'
        '[project.entry-points."forzium.plugins"]\n'
        f"{name} = '{name}:register'\n"
    )


def _cmd_bench(args) -> None:
    """Run tensor benchmarks and print JSON metrics."""

    from core.service import gpu

    size = args.size
    a = [[float(i + j) for j in range(size)] for i in range(size)]
    b = [[float((i * j) % 5) for j in range(size)] for i in range(size)]
    k = min(3, size)
    kernel = [[1.0] * k for _ in range(k)]
    metrics = gpu.benchmark_tensor_ops(a, b, kernel)
    print(json.dumps(metrics, indent=2))


def _load_plugins(sub) -> None:
    try:
        import forzium.plugins as plugins
    except Exception:
        plugins = None
    if plugins:
        for _, name, _ in pkgutil.iter_modules(plugins.__path__):
            module = import_module(f"forzium.plugins.{name}")
            if hasattr(module, "register"):
                module.register(sub)
    for ep in entry_points().select(group="forzium.plugins"):
        module = ep.load()
        if hasattr(module, "register"):
            module.register(sub)


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
    bench.set_defaults(func=_cmd_bench)
    plugin = sub.add_parser("plugin")
    plugin.add_argument("path")
    plugin.add_argument("name")
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
