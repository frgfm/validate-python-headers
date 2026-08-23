# Copyright (C) 2022-2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

import argparse
import io
import json
import os
import re
import stat
import sys
import tempfile
import tokenize
import tomllib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Union, cast

SHEBANG = ["#!usr/bin/python\n"]
BLANK_LINE = "\n"
CONFIG_SECTION = "[tool.validate-python-headers]"
CONFIG_KEYS = {"owner", "starting-year", "license", "license-notice", "paths", "ignore-files", "ignore-folders"}
COPYRIGHT_RE = re.compile(r"^# Copyright \(C\) (?P<years>(?P<start>\d{4})(?:-(?P<end>\d{4}))?), (?P<owner>.*)\.$")

# https://raw.githubusercontent.com/spdx/license-list-data/v3.17/json/licenses.json
with Path(__file__).parent.joinpath("supported-licenses.json").open("rb") as f:
    raw_data = json.load(f)
LICENSES: Dict[str, Dict[str, str]] = {
    license_["licenseId"]: {"name": license_["name"], "urls": license_["seeAlso"]} for license_ in raw_data["licenses"]
}


def get_header_options(
    owner: str,
    starting_year: int,
    license_id: Union[str, None],
    license_notice: Union[str, None],
    current_year: Union[int, None] = None,
    license_path: Path = Path("LICENSE"),
) -> List[List[str]]:
    current_year = datetime.now().year if current_year is None else current_year
    if starting_year < 1000 or starting_year > current_year:
        raise ValueError(f"Invalid first copyright year: {starting_year}")
    if len(owner) == 0 or "\n" in owner or "\r" in owner:
        raise ValueError("Please specify a single-line copyright owner")

    license_notices = []
    if isinstance(license_id, str) and len(license_id) > 0:
        license_info = LICENSES.get(license_id)
        if not isinstance(license_info, dict):
            raise ValueError(f"Invalid license identifier: {license_id}")
        if not license_path.is_file():
            raise FileNotFoundError("Unable to locate local copy of license text.")
        license_notices = [
            [
                f"# This program is licensed under the {license_info['name']}.\n",
                f"# See LICENSE or go to <{url}> for full license details.\n",
            ]
            for url in license_info["urls"]
        ]
    elif isinstance(license_notice, str) and len(license_notice) > 0:
        if not Path(license_notice).is_file():
            raise FileNotFoundError("Unable to locate the text of the license notice.")
        with Path(license_notice).open("r", encoding="utf-8") as f:
            license_notices = [f.readlines()]
    else:
        raise ValueError("One of the following args needs to be specified: 'license_id', 'license_notice'")

    year_options = [f"{current_year}"] + [f"{year}-{current_year}" for year in range(starting_year, current_year)]
    # Last element is the example for the error message.
    year_options.append(f"{current_year}" if starting_year == current_year else f"<FILE_CREATION_YEAR>-{current_year}")
    copyright_notices = [[f"# Copyright (C) {year_str}, {owner}.\n"] for year_str in year_options]

    return (
        [
            [*SHEBANG, BLANK_LINE, *copyright_notice, BLANK_LINE, *license_notice]
            for copyright_notice in copyright_notices[:-1]
            for license_notice in license_notices
        ]
        + [
            [*copyright_notice, BLANK_LINE, *license_notice]
            for copyright_notice in copyright_notices[:-1]
            for license_notice in license_notices
        ]
        + [[*copyright_notices[-1], BLANK_LINE, *license_notices[0]]]
    )


def discover_files(paths: List[str], ignore_files: List[str], ignore_folders: List[str]) -> List[Path]:
    if not paths:
        raise ValueError("Please specify at least one path to inspect")

    ignored_files = set(ignore_files)
    ignored_folders = {Path(folder) for folder in ignore_folders}
    source_paths: Dict[Path, None] = {}
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_file():
            candidates = [path]
        elif path.is_dir():
            candidates = sorted(path.rglob("*.py"))
        else:
            raise FileNotFoundError(f"Invalid path: {raw_path}")

        for source_path in candidates:
            if source_path.name in ignored_files or any(
                ignored_folder == source_path or ignored_folder in source_path.parents
                for ignored_folder in ignored_folders
            ):
                continue
            source_paths[source_path] = None
    return list(source_paths)


def _decode_source(raw_source: bytes) -> str:
    encoding, _ = tokenize.detect_encoding(io.BytesIO(raw_source).readline)
    return raw_source.decode(encoding)


def is_valid_header(raw_source: bytes, header_options: List[List[str]]) -> bool:
    try:
        source = _decode_source(raw_source).replace("\r\n", "\n").replace("\r", "\n")
    except (SyntaxError, UnicodeDecodeError):
        return False
    return any(source.startswith("".join(option)) for option in header_options[:-1])


def _atomic_write(source_path: Path, content: bytes) -> None:
    source_mode = stat.S_IMODE(source_path.stat().st_mode)
    file_descriptor, temporary_name = tempfile.mkstemp(prefix=f".{source_path.name}.", dir=source_path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        temporary_path.chmod(source_mode)
        temporary_path.replace(source_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def repair_header(
    source_path: Path,
    owner: str,
    starting_year: int,
    current_year: int,
    header_options: List[List[str]],
) -> bool:
    raw_source = source_path.read_bytes()
    try:
        decoded_lines = _decode_source(raw_source).splitlines(keepends=True)
    except (SyntaxError, UnicodeDecodeError):
        return False
    raw_lines = raw_source.splitlines(keepends=True)
    if len(decoded_lines) != len(raw_lines):
        return False

    matches = []
    for index, line in enumerate(decoded_lines):
        match = COPYRIGHT_RE.fullmatch(line.rstrip("\r\n"))
        if match is not None and match.group("owner") == owner:
            matches.append((index, match))
    if len(matches) != 1:
        return False

    line_index, match = matches[0]
    start_year = int(match.group("start"))
    end_year = int(match.group("end")) if match.group("end") is not None else None
    if start_year < starting_year or start_year >= current_year:
        return False
    if end_year is not None and (end_year < start_year or end_year >= current_year):
        return False

    old_years = match.group("years").encode("ascii")
    prefix = b"# Copyright (C) "
    needle = prefix + old_years + b", "
    raw_line = raw_lines[line_index]
    if raw_line.count(needle) != 1:
        return False
    year_start = raw_line.index(needle) + len(prefix)
    replacement = f"{start_year}-{current_year}".encode("ascii")
    raw_lines[line_index] = raw_line[:year_start] + replacement + raw_line[year_start + len(old_years) :]
    repaired_source = b"".join(raw_lines)
    if not is_valid_header(repaired_source, header_options):
        return False

    _atomic_write(source_path, repaired_source)
    return True


def run(args, current_year: Union[int, None] = None) -> tuple[List[Path], List[str]]:
    current_year = datetime.now().year if current_year is None else current_year
    if args.mode not in {"check", "fix"}:
        raise ValueError(f"Invalid mode '{args.mode}': expected 'check' or 'fix'")

    header_options = get_header_options(
        args.owner,
        args.year,
        args.license,
        args.license_notice,
        current_year,
        getattr(args, "license_path", Path("LICENSE")),
    )
    source_paths = discover_files(args.paths, args.ignore_files, args.ignore_folders)
    if args.mode == "fix":
        for source_path in source_paths:
            if not is_valid_header(source_path.read_bytes(), header_options):
                repair_header(source_path, args.owner, args.year, current_year, header_options)

    invalid_files = [
        source_path for source_path in source_paths if not is_valid_header(source_path.read_bytes(), header_options)
    ]
    return invalid_files, header_options[-1]


def write_issues(invalid_files: List[Path]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path is not None:
        issues = json.dumps([path.as_posix() for path in invalid_files], separators=(",", ":"))
        with Path(output_path).open("a", encoding="utf-8") as output_file:
            output_file.write(f"issues={issues}\n")


def _find_pyproject(config_path: Union[str, None]) -> Union[Path, None]:
    if config_path is not None:
        path = Path(config_path)
        if not path.is_file():
            raise FileNotFoundError(f"Invalid configuration path: {config_path}")
        return path

    for directory in (Path.cwd(), *Path.cwd().parents):
        candidate = directory / "pyproject.toml"
        if candidate.is_file():
            return candidate
    return None


def load_configuration(config_path: Union[str, None] = None) -> tuple[Dict[str, object], Path]:
    path = _find_pyproject(config_path)
    if path is None:
        return {}, Path.cwd()

    with path.open("rb") as config_file:
        document = tomllib.load(config_file)
    tool_config = document.get("tool", {})
    if not isinstance(tool_config, dict):
        raise ValueError(f"Invalid [tool]: expected a table in {path}")
    config = tool_config.get("validate-python-headers", {})
    if not isinstance(config, dict):
        raise ValueError(f"Invalid {CONFIG_SECTION}: expected a table in {path}")

    unknown_keys = sorted(set(config) - CONFIG_KEYS)
    if unknown_keys:
        key = unknown_keys[0]
        raise ValueError(f"Invalid {CONFIG_SECTION}.{key}: unknown key in {path}")

    for key in ("owner", "license", "license-notice"):
        if key in config and (not isinstance(config[key], str) or not config[key]):
            raise ValueError(f"Invalid {CONFIG_SECTION}.{key}: expected a non-empty string in {path}")
    if "starting-year" in config and (
        not isinstance(config["starting-year"], int)
        or isinstance(config["starting-year"], bool)
        or config["starting-year"] < 1000
    ):
        raise ValueError(f"Invalid {CONFIG_SECTION}.starting-year: expected a four-digit integer in {path}")
    for key in ("paths", "ignore-files", "ignore-folders"):
        if key in config and (
            not isinstance(config[key], list) or any(not isinstance(value, str) or not value for value in config[key])
        ):
            raise ValueError(f"Invalid {CONFIG_SECTION}.{key}: expected an array of non-empty strings in {path}")
    if "paths" in config and not config["paths"]:
        raise ValueError(f"Invalid {CONFIG_SECTION}.paths: expected at least one path in {path}")
    return config, path.parent


def _split_values(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def resolve_args(args):
    config, project_root = load_configuration(args.config)
    owner = args.owner if args.owner is not None else config.get("owner")
    year = args.starting_year if args.starting_year is not None else config.get("starting-year")
    if not isinstance(owner, str) or not owner:
        raise ValueError(f"Missing {CONFIG_SECTION}.owner; set it in pyproject.toml or pass --owner")
    if not isinstance(year, int) or isinstance(year, bool):
        raise ValueError(f"Missing {CONFIG_SECTION}.starting-year; set it in pyproject.toml or pass --starting-year")

    if args.license is not None or args.license_notice is not None:
        license_id = args.license or None
        license_notice = args.license_notice or None
    else:
        license_id = config.get("license")
        license_notice = config.get("license-notice")
        if isinstance(license_notice, str):
            license_notice = os.path.relpath(project_root / license_notice, Path.cwd())
    if bool(license_id) == bool(license_notice):
        raise ValueError(
            f"Configure exactly one of {CONFIG_SECTION}.license or {CONFIG_SECTION}.license-notice, "
            "or pass one matching CLI option"
        )

    if args.paths and args.folders is not None:
        raise ValueError("Pass explicit paths or --folders, not both")
    paths: List[str]
    if args.paths:
        paths = args.paths
    elif args.folders is not None:
        paths = _split_values(args.folders)
    else:
        configured_paths = cast(List[str], config.get("paths", ["."]))
        paths = [os.path.relpath(project_root / path, Path.cwd()) for path in configured_paths]
    ignore_files: List[str]
    ignore_files = (
        _split_values(args.ignore_files)
        if args.ignore_files is not None
        else cast(List[str], config.get("ignore-files", ["__init__.py"]))
    )
    configured_ignore_folders = cast(List[str], config.get("ignore-folders", [".github"]))
    ignore_folders = (
        _split_values(args.ignore_folders)
        if args.ignore_folders is not None
        else [os.path.relpath(project_root / folder, Path.cwd()) for folder in configured_ignore_folders]
    )
    if not paths:
        raise ValueError(f"Invalid {CONFIG_SECTION}.paths: expected at least one path")

    args.owner = owner
    args.year = year
    args.license = license_id
    args.license_notice = license_notice
    args.license_path = project_root / "LICENSE"
    args.paths = list(paths)
    args.ignore_files = list(ignore_files)
    args.ignore_folders = list(ignore_folders)
    return args


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

    parser = argparse.ArgumentParser(
        description="Keep Python files connected to the copyright owner and license your project declares.",
        epilog="Configure once in [tool.validate-python-headers], then run: %(prog)s check",
    )
    commands = parser.add_subparsers(dest="mode", required=True)
    for mode in ("check", "fix"):
        command = commands.add_parser(mode, parents=[common], help=f"{mode} copyright and license headers")
        command.add_argument("paths", nargs="*", help="files or folders; defaults to configured paths")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    try:
        args = resolve_args(parse_args(argv))
        invalid_files, example = run(args)
    except (FileNotFoundError, OSError, ValueError, tomllib.TOMLDecodeError) as error:
        write_issues([])
        sys.stderr.write(f"error: {error}\n")
        return 2

    write_issues(invalid_files)
    if invalid_files:
        invalid_str = "\n- " + "\n- ".join(map(str, invalid_files))
        invalid_str += "\n\nYour header should look like:\n\n" + "".join(example)
        sys.stderr.write(f"Invalid header in the following files:{invalid_str}\n")
        return 1
    return 0
