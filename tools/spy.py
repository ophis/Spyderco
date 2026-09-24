"""CLI entry point for the Spyderco catalog tool."""

import argparse
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from lib import catalog, images, sources, update, verify  # noqa: E402  (import after sys.path setup above)

# Modules registering subcommands via register(subparsers).
SUBCOMMAND_MODULES = [catalog, update, sources, images, verify]


def build_parser():
    parser = argparse.ArgumentParser(prog="spy")
    subparsers = parser.add_subparsers(dest="command")
    for module in SUBCOMMAND_MODULES:
        module.register(subparsers)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
