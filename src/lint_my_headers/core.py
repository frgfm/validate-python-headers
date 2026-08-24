# Copyright (C) 2022-2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import stat
import tempfile
import tokenize
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

COPYRIGHT_RE = re.compile(r"^# Copyright \(C\) (?P<years>(?P<start>\d{4})(?:-(?P<end>\d{4}))?), (?P<owner>.*)\.$")
COOKIE_RE = re.compile(r"^[ \t\f]*#.*?coding[:=][ \t]*([-_.a-zA-Z0-9]+)")
COPYRIGHT_PREFIX = "# Copyright (C) "
REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)


@dataclass(frozen=True)
class Diagnostic:
    path: str
    line: int
    column: int
    code: str
    message: str
    fixable: bool


@dataclass(frozen=True)
class CommandError:
    code: str
    message: str
    path: str | None = None


@dataclass
class CommandResult:
    command: str
    config_path: str | None
    checked: int
    changed: list[str]
    diagnostics: list[Diagnostic]
    expected_header: str | None
    error: CommandError | None = None

    @property
    def exit_code(self) -> int:
        if self.error is not None:
            return 2
        return 1 if self.diagnostics else 0

    def as_json(self, tool_version: str) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "tool_version": tool_version,
            "command": self.command,
            "config_path": self.config_path,
            "checked": self.checked,
            "changed": self.changed,
            "diagnostics": [asdict(diagnostic) for diagnostic in self.diagnostics],
            "expected_header": self.expected_header,
            "error": None if self.error is None else asdict(self.error),
        }


@dataclass(frozen=True)
class LicenseVariant:
    name: str
    urls: tuple[str, ...]

    def notices(self) -> list[tuple[str, ...]]:
        return [
            (
                f"# This program is licensed under the {self.name}.",
                f"# See LICENSE or go to <{url}> for full license details.",
            )
            for url in self.urls
        ]


@dataclass(frozen=True)
class HeaderPolicy:
    owner: str
    starting_year: int
    current_year: int
    notices: tuple[tuple[str, ...], ...]

    @property
    def expected_header(self) -> str:
        years = (
            str(self.current_year)
            if self.starting_year == self.current_year
            else f"<FILE_CREATION_YEAR>-{self.current_year}"
        )
        return "\n".join([f"# Copyright (C) {years}, {self.owner}.", "", *self.notices[0]]) + "\n"


@dataclass(frozen=True)
class FileIdentity:
    device: int
    inode: int
    mode: int
    links: int
    size: int
    mtime_ns: int
    digest: str


@dataclass(frozen=True)
class Analysis:
    diagnostic: Diagnostic | None
    line_index: int | None = None
    old_years: str | None = None
    start_year: int | None = None


def _load_license_data() -> tuple[dict[str, LicenseVariant], dict[str, LicenseVariant]]:
    package_dir = Path(__file__).parent
    with package_dir.joinpath("supported-licenses.json").open("rb") as stream:
        current_document = json.load(stream)
    compatibility_path = package_dir / "supported-license-compatibility.json"
    compatibility_document = (
        json.loads(compatibility_path.read_text(encoding="utf-8")) if compatibility_path.is_file() else {}
    )
    current = {
        item["licenseId"]: LicenseVariant(item["name"], tuple(item["seeAlso"])) for item in current_document["licenses"]
    }
    compatibility = {
        identifier: LicenseVariant(item["name"], tuple(item["urls"]))
        for identifier, item in compatibility_document.items()
    }
    return current, compatibility


LICENSES, LEGACY_LICENSES = _load_license_data()


def build_policy(
    owner: str,
    starting_year: int,
    license_id: str | None,
    license_notice: str | None,
    *,
    current_year: int | None = None,
    license_path: Path = Path("LICENSE"),
) -> HeaderPolicy:
    year = datetime.now().year if current_year is None else current_year
    if starting_year < 1000 or starting_year > year:
        raise ValueError(f"Invalid first copyright year: {starting_year}")
    if not owner or "\n" in owner or "\r" in owner:
        raise ValueError("Please specify a single-line copyright owner")

    notices: list[tuple[str, ...]] = []
    if license_id:
        variants = [variant for variant in (LICENSES.get(license_id), LEGACY_LICENSES.get(license_id)) if variant]
        if not variants:
            raise ValueError(f"Invalid license identifier: {license_id}")
        if not license_path.is_file():
            raise FileNotFoundError("Unable to locate local copy of license text.")
        for variant in variants:
            notices.extend(variant.notices())
    elif license_notice:
        notice_path = Path(license_notice)
        if not notice_path.is_file():
            raise FileNotFoundError("Unable to locate the text of the license notice.")
        lines = tuple(notice_path.read_text(encoding="utf-8").splitlines())
        if not lines:
            raise ValueError("The custom license notice must not be empty")
        notices.append(lines)
    else:
        raise ValueError("One of the following args needs to be specified: 'license', 'license-notice'")

    return HeaderPolicy(owner, starting_year, year, tuple(dict.fromkeys(notices)))


def _is_reparse(file_stat: os.stat_result) -> bool:
    return bool(REPARSE_POINT and getattr(file_stat, "st_file_attributes", 0) & REPARSE_POINT)


def _is_symlink_or_reparse(path: Path) -> bool:
    file_stat = path.lstat()
    return stat.S_ISLNK(file_stat.st_mode) or _is_reparse(file_stat)


def _path_is_safe(path: Path) -> bool:
    absolute = path.absolute()
    try:
        file_stat = absolute.lstat()
        if not stat.S_ISREG(file_stat.st_mode) or _is_reparse(file_stat) or file_stat.st_nlink != 1:
            return False
        for parent in absolute.parents:
            if parent == Path(parent.anchor):
                break
            if _is_symlink_or_reparse(parent):
                return False
    except OSError:
        return False
    return True


def _identity(path: Path, raw_source: bytes) -> FileIdentity | None:
    if not _path_is_safe(path):
        return None
    file_stat = path.lstat()
    return FileIdentity(
        file_stat.st_dev,
        file_stat.st_ino,
        file_stat.st_mode,
        file_stat.st_nlink,
        file_stat.st_size,
        file_stat.st_mtime_ns,
        hashlib.sha256(raw_source).hexdigest(),
    )


def _identity_matches(path: Path, identity: FileIdentity) -> bool:
    try:
        file_stat = path.lstat()
        current = (
            file_stat.st_dev,
            file_stat.st_ino,
            file_stat.st_mode,
            file_stat.st_nlink,
            file_stat.st_size,
            file_stat.st_mtime_ns,
        )
        expected = (
            identity.device,
            identity.inode,
            identity.mode,
            identity.links,
            identity.size,
            identity.mtime_ns,
        )
        return current == expected and hashlib.sha256(path.read_bytes()).hexdigest() == identity.digest
    except OSError:
        return False


def _decode_source(raw_source: bytes) -> tuple[list[str], list[bytes], int]:
    encoding, consumed = tokenize.detect_encoding(io.BytesIO(raw_source).readline)
    decoded = raw_source.decode(encoding).replace("\r\n", "\n").replace("\r", "\n")
    lines = decoded.splitlines()
    raw_lines = raw_source.splitlines(keepends=True)
    if len(lines) != len(raw_lines) and not (decoded.endswith("\n") and len(lines) + 1 == len(raw_lines)):
        raise UnicodeDecodeError(encoding, raw_source, 0, len(raw_source), "line mapping is ambiguous")

    cookie_index = next(
        (index for index, line in enumerate(lines[: len(consumed)]) if COOKIE_RE.match(line)),
        None,
    )
    shebang_index = 0 if lines and lines[0].startswith("#!") else None
    indexes = [index for index in (cookie_index, shebang_index) if index is not None]
    preamble_end = max(indexes) + 1 if indexes else 0
    if preamble_end and preamble_end < len(lines) and lines[preamble_end] == "":
        preamble_end += 1
    return lines, raw_lines, preamble_end


def _diagnostic(path: str, line: int, code: str, message: str, *, fixable: bool = False) -> Diagnostic:
    return Diagnostic(path, max(1, line), 1, code, message, fixable)


def analyze_bytes(raw_source: bytes, policy: HeaderPolicy, path: Path, display_path: str) -> Analysis:
    try:
        lines, raw_lines, header_index = _decode_source(raw_source)
    except (LookupError, SyntaxError, UnicodeDecodeError) as error:
        return Analysis(_diagnostic(display_path, 1, "LMH007", f"Python source encoding cannot be decoded: {error}"))

    candidates = [index for index, line in enumerate(lines) if line.startswith("# Copyright")]
    if not candidates:
        partial_notice = any("licensed under" in line or "full license details" in line for line in lines)
        code = "LMH006" if partial_notice else "LMH001"
        message = "legal header is incomplete or misplaced" if partial_notice else "legal header is missing"
        return Analysis(_diagnostic(display_path, header_index + 1, code, message))
    if len(candidates) > 1:
        return Analysis(_diagnostic(display_path, candidates[1] + 1, "LMH006", "legal header is duplicated"))

    line_index = candidates[0]
    if line_index != header_index:
        return Analysis(_diagnostic(display_path, line_index + 1, "LMH006", "legal header is misplaced"))
    match = COPYRIGHT_RE.fullmatch(lines[line_index])
    if match is None:
        return Analysis(_diagnostic(display_path, line_index + 1, "LMH006", "copyright line is malformed"))
    if line_index + 1 >= len(lines) or lines[line_index + 1] != "":
        return Analysis(
            _diagnostic(
                display_path,
                line_index + 2,
                "LMH006",
                "copyright and license notice must be separated by one blank line",
            )
        )
    if match.group("owner") != policy.owner:
        return Analysis(
            _diagnostic(
                display_path,
                line_index + 1,
                "LMH002",
                f"copyright owner is {match.group('owner')!r}; expected {policy.owner!r}",
            )
        )

    start_year = int(match.group("start"))
    end_group = match.group("end")
    end_year = int(end_group) if end_group is not None else None
    invalid_year = (
        start_year < policy.starting_year
        or start_year > policy.current_year
        or (end_year is not None and (end_year < start_year or end_year > policy.current_year))
        or (end_year is not None and start_year == policy.current_year)
    )
    if invalid_year:
        return Analysis(
            _diagnostic(
                display_path,
                line_index + 1,
                "LMH003",
                f"copyright year {match.group('years')} is outside {policy.starting_year}-{policy.current_year}",
            )
        )

    notice_index = line_index + 2
    if not any(tuple(lines[notice_index : notice_index + len(notice)]) == notice for notice in policy.notices):
        return Analysis(
            _diagnostic(
                display_path,
                notice_index + 1,
                "LMH005",
                "license notice is missing or does not match the configured license",
            )
        )

    is_current = start_year == policy.current_year if end_year is None else end_year == policy.current_year
    if is_current:
        return Analysis(None)
    diagnostic = _diagnostic(
        display_path,
        line_index + 1,
        "LMH004",
        f"copyright year ends before {policy.current_year}",
        fixable=_path_is_safe(path),
    )
    if line_index >= len(raw_lines):
        return Analysis(
            _diagnostic(display_path, line_index + 1, "LMH006", "raw copyright line cannot be mapped safely")
        )
    return Analysis(diagnostic, line_index, match.group("years"), start_year)


def _atomic_replace(path: Path, content: bytes, identity: FileIdentity) -> bool:
    if not _identity_matches(path, identity):
        return False
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        temporary_path.chmod(stat.S_IMODE(identity.mode))
        if not _identity_matches(path, identity):
            return False
        temporary_path.replace(path)
        return True
    finally:
        temporary_path.unlink(missing_ok=True)


def repair_stale_header(path: Path, raw_source: bytes, analysis: Analysis, policy: HeaderPolicy) -> bool:
    if analysis.line_index is None or analysis.old_years is None or analysis.start_year is None:
        return False
    identity = _identity(path, raw_source)
    if identity is None:
        return False

    raw_lines = raw_source.splitlines(keepends=True)
    raw_line = raw_lines[analysis.line_index]
    old_years = analysis.old_years.encode("ascii")
    prefix = COPYRIGHT_PREFIX.encode("ascii")
    needle = prefix + old_years + b", "
    if raw_line.count(needle) != 1:
        return False
    year_start = raw_line.index(needle) + len(prefix)
    replacement = f"{analysis.start_year}-{policy.current_year}".encode("ascii")
    raw_lines[analysis.line_index] = raw_line[:year_start] + replacement + raw_line[year_start + len(old_years) :]
    repaired = b"".join(raw_lines)
    if analyze_bytes(repaired, policy, path, "<repaired>").diagnostic is not None:
        return False
    return _atomic_replace(path, repaired, identity)


def _ignored(path: Path, ignore_files: set[str], ignore_folders: list[Path]) -> bool:
    if path.name in ignore_files:
        return True
    absolute = Path(
        os.path.normcase(os.path.abspath(path))  # ruff: ignore[os-path-abspath] - preserve lexical symlinks.
    )
    return any(absolute == folder or folder in absolute.parents for folder in ignore_folders)


def discover_files(paths: list[str], ignore_files: list[str], ignore_folders: list[str]) -> list[Path]:
    if not paths:
        raise ValueError("Please specify at least one path to inspect")
    ignored_names = set(ignore_files)
    ignored_directories = [
        Path(os.path.normcase(os.path.abspath(folder)))  # ruff: ignore[os-path-abspath] - preserve lexical symlinks.
        for folder in ignore_folders
    ]
    selected: dict[str, Path] = {}

    for raw_path in paths:
        path = Path(os.path.normpath(raw_path))
        try:
            path_stat = path.lstat()
        except OSError as error:
            raise FileNotFoundError(f"Invalid path: {raw_path}") from error
        if (stat.S_ISLNK(path_stat.st_mode) or _is_reparse(path_stat)) and path.is_dir():
            raise ValueError(f"Explicit directory must not be a symlink or reparse point: {raw_path}")
        if path.is_file():
            candidates = [path]
        elif path.is_dir():
            candidates = []
            for directory, folder_names, file_names in os.walk(path, followlinks=False):
                directory_path = Path(directory)
                folder_names[:] = sorted(
                    name
                    for name in folder_names
                    if not _is_symlink_or_reparse(directory_path / name)
                    and not _ignored(directory_path / name, set(), ignored_directories)
                )
                for file_name in sorted(file_names):
                    candidate = directory_path / file_name
                    if candidate.suffix == ".py" and not _is_symlink_or_reparse(candidate):
                        candidates.append(candidate)
        else:
            raise FileNotFoundError(f"Invalid path: {raw_path}")

        for candidate in candidates:
            if _ignored(candidate, ignored_names, ignored_directories):
                continue
            key = os.path.normcase(
                os.path.abspath(candidate)  # ruff: ignore[os-path-abspath] - lexical deduplication.
            )
            selected.setdefault(key, candidate)
    return list(selected.values())


def display_path(path: Path, project_root: Path) -> str:
    return Path(os.path.relpath(path.absolute(), project_root.absolute())).as_posix()


def run(args: Any, current_year: int | None = None) -> CommandResult:
    if args.mode not in {"check", "fix"}:
        raise ValueError(f"Invalid mode {args.mode!r}: expected 'check' or 'fix'")
    policy = build_policy(
        args.owner,
        args.year,
        args.license,
        args.license_notice,
        current_year=current_year,
        license_path=args.license_path,
    )
    result = CommandResult(
        command=args.mode,
        config_path=args.config_display,
        checked=0,
        changed=[],
        diagnostics=[],
        expected_header=policy.expected_header,
    )
    try:
        source_paths = discover_files(args.paths, args.ignore_files, args.ignore_folders)
        source_paths.sort(key=lambda path: display_path(path, args.project_root))
    except (OSError, ValueError) as error:
        result.error = CommandError("LMH900", str(error))
        return result

    for source_path in source_paths:
        shown_path = display_path(source_path, args.project_root)
        try:
            raw_source = source_path.read_bytes()
            analysis = analyze_bytes(raw_source, policy, source_path, shown_path)
            result.checked += 1
            if analysis.diagnostic is None:
                continue
            if args.mode == "fix" and analysis.diagnostic.code == "LMH004":
                if not analysis.diagnostic.fixable or not repair_stale_header(
                    source_path, raw_source, analysis, policy
                ):
                    result.diagnostics.append(
                        _diagnostic(
                            shown_path,
                            analysis.diagnostic.line,
                            "LMH008",
                            "repair target is not a safe single-link regular file",
                        )
                    )
                    continue
                result.changed.append(shown_path)
                repaired_analysis = analyze_bytes(source_path.read_bytes(), policy, source_path, shown_path)
                if repaired_analysis.diagnostic is not None:
                    result.diagnostics.append(repaired_analysis.diagnostic)
                continue
            result.diagnostics.append(analysis.diagnostic)
        except OSError as error:
            result.error = CommandError("LMH900", str(error), shown_path)
            break

    result.changed.sort()
    result.diagnostics.sort(key=lambda item: (item.path, item.line, item.column, item.code))
    return result
