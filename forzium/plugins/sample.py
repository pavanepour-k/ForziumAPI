"""Sample plugin used for tests."""

import logging

LOGGER = logging.getLogger("forzium.plugins.sample")


def register(subparsers) -> None:
    parser = subparsers.add_parser("hello")
    parser.set_defaults(func=_run)


def _run(args) -> None:
    LOGGER.info("hello plugin")
