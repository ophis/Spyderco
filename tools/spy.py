"""CLI entry point for the Spyderco catalog tool."""

import argparse
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from lib import images, render, sources, update, verify  # noqa: E402  (import after sys.path setup above)

# Modules registering subcommands via register(subparsers).
SUBCOMMAND_MODULES = [render, update, sources, images, verify]


def _cmd_seed(args):
    from migrate import seed

    seed.print_report(seed.seed(force=args.force, ref_dir=Path(args.ref)))
    return 0


def _register_seed(subparsers):
    parser = subparsers.add_parser("seed-from-md", help="one-time: build families/ from the current catalogs")
    parser.add_argument("--ref", required=True, help="directory holding the old scripts' data (wt_*.txt, imgs.json, ...)")
    parser.add_argument("--force", action="store_true", help="overwrite existing family files")
    parser.set_defaults(func=_cmd_seed)


def build_parser():
    parser = argparse.ArgumentParser(prog="spy")
    subparsers = parser.add_subparsers(dest="command")
    for module in SUBCOMMAND_MODULES:
        module.register(subparsers)
    _register_seed(subparsers)
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
