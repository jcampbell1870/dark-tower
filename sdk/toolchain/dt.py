#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PRINT_RE = re.compile(r'print\("((?:\\.|[^"\\])*)"\)\s*;')


class DtlError(Exception):
    pass


def _decode_string(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return value


def extract_prints(source: str) -> list[str]:
    return [_decode_string(match.group(1)) for match in PRINT_RE.finditer(source)]


def read_source(path: Path) -> str:
    if not path.exists():
        raise DtlError(f"source file not found: {path}")
    if not path.is_file():
        raise DtlError(f"source path is not a file: {path}")
    return path.read_text(encoding="utf-8")


def run_command(source_path: Path) -> int:
    source = read_source(source_path)
    outputs = extract_prints(source)
    if not outputs:
        raise DtlError(f"no runnable output found in {source_path}")
    for value in outputs:
        sys.stdout.write(value)
    return 0


def build_command(source_path: Path, output_path: Path) -> int:
    source = read_source(source_path)
    outputs = extract_prints(source)
    artifact = {
        "format": "dtl-prototype-v0.2",
        "source": str(source_path),
        "prints": outputs,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return 0


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dt",
        description="Dark Tower Language (DTL) prototype CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a DTL source file")
    run_parser.add_argument("source", help="Path to a .dt source file")

    build_parser = subparsers.add_parser("build", help="Build a DTL source file")
    build_parser.add_argument("source", help="Path to a .dt source file")
    build_parser.add_argument("-o", "--output", required=True, help="Output artifact path")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "run":
            return run_command(Path(args.source))
        if args.command == "build":
            return build_command(Path(args.source), Path(args.output))
    except DtlError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
