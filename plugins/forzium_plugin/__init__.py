"""CLI plugin exposing a scaffold command."""


def register(subparsers) -> None:
    parser = subparsers.add_parser("scaffold")
    parser.add_argument("path")
    parser.add_argument("name")

    def _run(args) -> None:
        from forzium.cli import scaffold_plugin

        scaffold_plugin(args.path, args.name)

    parser.set_defaults(func=_run)
