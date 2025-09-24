"""Sample Forzium CLI plugin demonstrating registration mechanics."""

from __future__ import annotations

import argparse
from typing import Callable


def _handle_plugin(_: argparse.Namespace) -> None:
    """Display a friendly greeting from the sample plugin."""

    print("forzium plugin")


def register(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> Callable[[argparse.Namespace], None]:
    """Register the sample `plugin` subcommand with the CLI."""

    parser = subparsers.add_parser(
        "plugin",
        help="Demonstration command installed by the Forzium sample plugin.",
    )
    parser.set_defaults(func=_handle_plugin)
    return _handle_plugin