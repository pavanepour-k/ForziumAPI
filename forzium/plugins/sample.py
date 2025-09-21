"""Sample plugin used for tests."""


def register(subparsers) -> None:
    parser = subparsers.add_parser("hello")
    parser.set_defaults(func=_run)


def _run(args) -> None:
    print("hello plugin")
