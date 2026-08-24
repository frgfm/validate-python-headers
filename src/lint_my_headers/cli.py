# Copyright (C) 2022-2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from importlib import metadata
from pathlib import Path

from .config import CONFIG_SECTION, resolve_args
from .core import CommandError, CommandResult, run

DISTRIBUTION_NAME = "lint-my-headers"


def tool_version() -> str:
    try:
        return metadata.version(DISTRIBUTION_NAME)
    except metadata.PackageNotFoundError:
        for parent in Path(__file__).parents:
            pyproject = parent / "pyproject.toml"
            if not pyproject.is_file():
                continue
            with pyproject.open("rb") as stream:
                project = tomllib.load(stream).get("project", {})
            if project.get("name") == DISTRIBUTION_NAME and isinstance(project.get("version"), str):
                return project["version"]
        return "unknown"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", help="path to pyproject.toml; defaults to the nearest one")
    common.add_argument("--owner", help="copyright owner; overrides pyproject.toml")
    common.add_argument("--starting-year", type=int, help="first copyright year; overrides pyproject.toml")
    common.add_argument("--license", help="SPDX license identifier; overrides pyproject.toml")
    common.add_argument("--license-notice", help="custom license notice path; overrides pyproject.toml")
    common.add_argument("--folders", help=argparse.SUPPRESS)
    common.add_argument("--ignore-files", help="comma-separated filenames; overrides pyproject.toml")
    common.add_argument("--ignore-folders", help="comma-separated folders; overrides pyproject.toml")
    common.add_argument("--output-format", choices=("text", "json"), default="text")

    parser = argparse.ArgumentParser(
        description="Check and safely update copyright and license headers in Python source files.",
        epilog=f"Configure once in {CONFIG_SECTION}, then run: %(prog)s check",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {tool_version()}")
    commands = parser.add_subparsers(dest="mode", required=True)
    for mode in ("check", "fix"):
        command = commands.add_parser(mode, parents=[common], help=f"{mode} copyright and license headers")
        command.add_argument("paths", nargs="*", help="files or folders; defaults to configured paths")
    return parser.parse_args(argv)


def _empty_error_result(args: argparse.Namespace, error: Exception) -> CommandResult:
    return CommandResult(
        command=args.mode,
        config_path=getattr(args, "config_display", None),
        checked=0,
        changed=[],
        diagnostics=[],
        expected_header=None,
        error=CommandError("LMH900", str(error)),
    )


def write_action_outputs(result: CommandResult) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path is None:
        return
    issues = [] if result.error is not None else sorted({diagnostic.path for diagnostic in result.diagnostics})
    with Path(output_path).open("a", encoding="utf-8") as output_file:
        output_file.write(f"issues={json.dumps(issues, separators=(',', ':'))}\n")
        output_file.write(f"changed={json.dumps(result.changed, separators=(',', ':'))}\n")


def _render_text(result: CommandResult) -> None:
    if result.error is not None:
        path = "" if result.error.path is None else f"{result.error.path}: "
        sys.stderr.write(f"error: {path}{result.error.message}\n")
    if not result.diagnostics:
        return
    for diagnostic in result.diagnostics:
        suffix = " [fixable]" if diagnostic.fixable else ""
        sys.stderr.write(
            f"{diagnostic.path}:{diagnostic.line}:{diagnostic.column}: {diagnostic.code} {diagnostic.message}{suffix}\n"
        )
    if result.expected_header is not None:
        sys.stderr.write(f"\nExpected header:\n\n{result.expected_header}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = run(resolve_args(args))
    except (FileNotFoundError, LookupError, OSError, ValueError, tomllib.TOMLDecodeError) as error:
        result = _empty_error_result(args, error)
    except Exception as error:  # ruff: ignore[blind-except] - unexpected failures use the LMH900 envelope.
        result = _empty_error_result(args, error)

    write_action_outputs(result)
    if args.output_format == "json":
        sys.stdout.write(json.dumps(result.as_json(tool_version()), sort_keys=True, separators=(",", ":")) + "\n")
    else:
        _render_text(result)
    return result.exit_code
