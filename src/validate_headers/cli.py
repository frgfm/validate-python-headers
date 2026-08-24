# Copyright (C) 2022-2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .config import (
    CONFIG_SECTION,
    _configuration_table,
    _find_pyproject,
    _split_values,
    load_configuration,
    resolve_args,
)
from .core import (
    CommandError,
    CommandResult,
    Diagnostic,
    DiagnosticCode,
    Settings,
    _decode_source,
    discover_files,
    get_header_options,
    is_valid_header,
    repair_header,
    run,
)

SCHEMA_VERSION = 1


def _tool_version() -> str:
    try:
        return version("validate-python-headers")
    except PackageNotFoundError:
        return "0+unknown"


def _display_path(path: Path, root: Path) -> str:
    absolute = path.absolute()
    try:
        return Path(os.path.relpath(absolute, root)).as_posix()
    except ValueError:
        return absolute.as_posix()


def _diagnostic_dict(diagnostic: Diagnostic, root: Path) -> dict[str, object]:
    return {
        "path": _display_path(diagnostic.path, root),
        "line": diagnostic.line,
        "column": diagnostic.column,
        "code": diagnostic.code.value,
        "message": diagnostic.message,
        "fixable": diagnostic.fixable,
    }


def _sorted_diagnostics(result: CommandResult) -> list[Diagnostic]:
    return sorted(
        result.diagnostics,
        key=lambda item: (
            _display_path(item.path, result.project_root),
            item.line,
            item.column,
            item.code.value,
        ),
    )


def result_dict(result: CommandResult) -> dict[str, object]:
    root = result.project_root
    error = None
    if result.error is not None:
        error = {
            "code": result.error.code,
            "message": result.error.message,
            "path": None if result.error.path is None else _display_path(result.error.path, root),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "tool_version": _tool_version(),
        "command": result.command,
        "config_path": None if result.config_path is None else _display_path(result.config_path, root),
        "checked": result.checked,
        "changed": sorted(_display_path(path, root) for path in result.changed),
        "diagnostics": [_diagnostic_dict(item, root) for item in _sorted_diagnostics(result)],
        "expected_header": result.expected_header,
        "error": error,
    }


def _write_action_outputs(result: CommandResult) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path is None:
        return
    issues = (
        []
        if result.error is not None
        else sorted({_display_path(item.path, result.project_root) for item in result.diagnostics})
    )
    changed = sorted({_display_path(path, result.project_root) for path in result.changed})
    with Path(output_path).open("a", encoding="utf-8") as output_file:
        output_file.write(f"issues={json.dumps(issues, separators=(',', ':'))}\n")
        output_file.write(f"changed={json.dumps(changed, separators=(',', ':'))}\n")


def write_issues(invalid_files: list[Path]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path is not None:
        issues = json.dumps([path.as_posix() for path in invalid_files], separators=(",", ":"))
        with Path(output_path).open("a", encoding="utf-8") as output_file:
            output_file.write(f"issues={issues}\n")


def _render_text(result: CommandResult) -> None:
    root = result.project_root
    if result.changed:
        sys.stdout.write("Updated headers:\n")
        for path in result.changed:
            sys.stdout.write(f"- {_display_path(path, root)}\n")
    if result.error is not None:
        path = "" if result.error.path is None else f" ({_display_path(result.error.path, root)})"
        sys.stderr.write(f"error: {result.error.message}{path}\n")
        return
    if not result.diagnostics:
        return
    for diagnostic in _sorted_diagnostics(result):
        fixable = " [fixable]" if diagnostic.fixable else ""
        sys.stderr.write(
            f"{_display_path(diagnostic.path, root)}:{diagnostic.line}:{diagnostic.column}: "
            f"{diagnostic.code.value} {diagnostic.message}{fixable}\n"
        )
    if result.expected_header is not None:
        sys.stderr.write(f"\nExpected header:\n\n{result.expected_header}\n")


def _render_json(result: CommandResult) -> None:
    sys.stdout.write(json.dumps(result_dict(result), ensure_ascii=False, separators=(",", ":")) + "\n")


def _error_result(args, error: Exception) -> CommandResult:
    config_path = None
    if args.config is not None:
        config_path = Path(args.config).absolute()
    return CommandResult(
        args.command,
        Path.cwd().resolve(),
        config_path,
        0,
        (),
        (),
        None,
        CommandError(str(error), config_path if isinstance(error, FileNotFoundError) else None),
    )


def parse_args(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", help="path to pyproject.toml; defaults to the nearest one")
    common.add_argument("--owner", help="copyright owner; overrides pyproject.toml")
    common.add_argument("--starting-year", type=int, help="first copyright year; overrides pyproject.toml")
    common.add_argument("--license", help="SPDX license identifier; overrides pyproject.toml")
    common.add_argument("--license-notice", help="custom license notice path; overrides pyproject.toml")
    common.add_argument("--folders", help=argparse.SUPPRESS)
    common.add_argument("--ignore-files", help="comma-separated filenames; overrides pyproject.toml")
    common.add_argument("--ignore-folders", help="comma-separated folders; overrides pyproject.toml")
    common.add_argument(
        "--output-format",
        choices=("text", "json"),
        default="text",
        help="diagnostic output format",
    )

    parser = argparse.ArgumentParser(
        description="Lint Python copyright and license headers and conservatively refresh recognized years.",
        epilog="Configure once in [tool.validate-python-headers], then run: %(prog)s check",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {_tool_version()}")
    commands = parser.add_subparsers(dest="command", required=True)
    for command_name in ("check", "fix"):
        command = commands.add_parser(
            command_name,
            parents=[common],
            help=f"{command_name} copyright and license headers",
        )
        command.add_argument("paths", nargs="*", help="files or folders; defaults to configured paths")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        settings = resolve_args(args)
        result = run(settings, args.command)
    except (FileNotFoundError, OSError, ValueError, tomllib.TOMLDecodeError) as error:
        result = _error_result(args, error)

    _write_action_outputs(result)
    if args.output_format == "json":
        _render_json(result)
    else:
        _render_text(result)
    return result.exit_code


__all__ = [
    "CONFIG_SECTION",
    "DiagnosticCode",
    "Settings",
    "_configuration_table",
    "_decode_source",
    "_find_pyproject",
    "_split_values",
    "discover_files",
    "get_header_options",
    "is_valid_header",
    "load_configuration",
    "main",
    "parse_args",
    "repair_header",
    "resolve_args",
    "result_dict",
    "run",
    "write_issues",
]
