# Copyright (C) 2022-2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

import io
import json
import os
import re
import stat
import sys
import tempfile
import tokenize
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Union

SHEBANG = ["#!usr/bin/python\n"]
BLANK_LINE = "\n"
COPYRIGHT_RE = re.compile(r"^# Copyright \(C\) (?P<years>(?P<start>\d{4})(?:-(?P<end>\d{4}))?), (?P<owner>.*)\.$")

# https://raw.githubusercontent.com/spdx/license-list-data/v3.17/json/licenses.json
with Path(__file__).parent.absolute().joinpath("supported-licenses.json").open("rb") as f:
    raw_data = json.load(f)
LICENSES: Dict[str, Dict[str, str]] = {
    _license["licenseId"]: {"name": _license["name"], "urls": _license["seeAlso"]} for _license in raw_data["licenses"]
}


def get_header_options(
    owner: str,
    starting_year: int,
    license_id: Union[str, None],
    license_notice: Union[str, None],
    current_year: Union[int, None] = None,
) -> List[List[str]]:
    current_year = datetime.now().year if current_year is None else current_year
    if starting_year > current_year:
        raise ValueError(f"Invalid first copyright year: {starting_year}")
    if len(owner) == 0 or "\n" in owner or "\r" in owner:
        raise ValueError("Please specify a single-line copyright owner")

    license_notices = []
    if isinstance(license_id, str) and len(license_id) > 0:
        license_info = LICENSES.get(license_id)
        if not isinstance(license_info, dict):
            raise ValueError(f"Invalid license identifier: {license_id}")
        if not Path("LICENSE").is_file():
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


def discover_files(folders: str, ignore_files: str, ignore_folders: str) -> List[Path]:
    folder_names = folders.split(",")
    if any(len(folder) == 0 for folder in folder_names):
        raise ValueError("Please specify at least one folder to inspect")

    ignored_files = {name for name in ignore_files.split(",") if name}
    ignored_folders = {Path(folder) for folder in ignore_folders.split(",") if folder}
    source_paths: Dict[Path, None] = {}
    for folder in folder_names:
        folder_path = Path(folder)
        if not folder_path.is_dir():
            raise FileNotFoundError(f"Invalid folder path: {folder}")
        for source_path in sorted(folder_path.rglob("*.py")):
            if source_path.name in ignored_files or any(
                ignored_folder in source_path.parents for ignored_folder in ignored_folders
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

    header_options = get_header_options(args.owner, args.year, args.license, args.license_notice, current_year)
    source_paths = discover_files(args.folders, args.ignore_files, args.ignore_folders)
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


def parse_args():
    import argparse

    parser = argparse.ArgumentParser(
        description="Header validator for your Python files", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("owner", type=str, help="name of the copyright owner")
    parser.add_argument("year", type=int, help="first copyright year of the project")
    parser.add_argument("--license", type=str, default=None, help="identifier of the license being used")
    parser.add_argument("--folders", type=str, default=".", help="folders to inspect")
    parser.add_argument("--ignore-files", type=str, default="", help="files to ignore")
    parser.add_argument("--ignore-folders", type=str, default="", help="folders to ignore")
    parser.add_argument("--license-notice", type=str, default=None, help="path to custom license notice")
    parser.add_argument("--mode", type=str, default="check", help="whether to check or fix headers")
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        invalid_files, example = run(args)
    except (FileNotFoundError, OSError, ValueError) as error:
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


if __name__ == "__main__":
    raise SystemExit(main())
