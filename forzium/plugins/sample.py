"""Sample plugin used for tests."""


def register(subparsers) -> None:
    parser = subparsers.add_parser("Sample")
    parser.set_defaults(func=_run)


def _run(args) -> None:
    print("Sample plugin")
