"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .builder import UnsafeOutputError, build
from .config import DEFAULT_OUTPUT, DEFAULT_SOURCE, BuildConfig


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="spinoza-build",
        description="Generate the Spinoza Ethics scholarly workbench site.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="unpacked EPUB working directory (default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="directory to write the site into (default: %(default)s)",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="write into an existing output directory instead of removing it first",
    )
    parser.add_argument(
        "--base-path",
        default="",
        help=(
            "URL path the site is served under, e.g. '/repo-name' for a GitHub "
            "Pages project page (default: served from a domain root)"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = BuildConfig.create(args.source, args.output, base_path=args.base_path)

    if not (config.source / "text").is_dir():
        print(
            f"error: no 'text' directory under {config.source}\n"
            "The build needs the unpacked EPUB working directory; pass --source.",
            file=sys.stderr,
        )
        return 2

    try:
        report = build(config, clean=not args.no_clean)
    except UnsafeOutputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
