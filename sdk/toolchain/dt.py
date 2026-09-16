#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PRINT_START_RE = re.compile(r'print\("')


class DtlError(Exception):
    pass


def _decode_string(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError as exc:
        raise DtlError(f"invalid string literal: {value}") from exc


def extract_prints(source: str) -> list[str]:
    outputs: list[str] = []
    position = 0

    while True:
        match = PRINT_START_RE.search(source, position)
        if match is None:
            break

        literal_start = match.end()
        index = literal_start

        while index < len(source):
            if source[index] == '"':
                backslash_count = 0
                lookback = index - 1
                while lookback >= literal_start and source[lookback] == "\\":
                    backslash_count += 1
                    lookback -= 1

                if backslash_count % 2 == 0:
                    literal = source[literal_start:index]
                    trailing = source[index + 1 :]
                    trailing_match = re.match(r"\s*\)\s*;", trailing)
                    if trailing_match is None:
                        raise DtlError("invalid print statement syntax")
                    outputs.append(_decode_string(literal))
                    position = index + 1 + trailing_match.end()
                    break

            index += 1
        else:
            raise DtlError("unterminated string literal in print statement")

    return outputs


def read_source(path: Path) -> str:
    if not path.exists():
        raise DtlError(f"source file not found: {path}")
    if not path.is_file():
        raise DtlError(f"source path is not a file: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise DtlError(f"source file is not valid UTF-8: {path}") from exc


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
    if not outputs:
        raise DtlError(f"no runnable output found in {source_path}")
    artifact = {
        "format": "dtl-prototype-v0.2",
        "source": str(source_path),
        "prints": outputs,
    }
    if output_path.exists() and output_path.is_dir():
        raise DtlError(f"output path is a directory: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        output_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise DtlError(f"unable to write output file: {output_path}") from exc
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
