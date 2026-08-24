# Copyright (C) 2026, François-Guillaume Fernandez.

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
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from pathlib import Path

BLANK_LINE = "\n"
COPYRIGHT_RE = re.compile(r"^# Copyright \(C\) (?P<years>(?P<start>\d{4})(?:-(?P<end>\d{4}))?), (?P<owner>.*)\.$")
CODING_RE = re.compile(r"^[ \t\f]*#.*?coding[:=][ \t]*[-_.a-zA-Z0-9]+")
COMMENT_OR_BLANK_RE = re.compile(r"^[ \t\f]*(?:[#\r\n]|$)")
REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

with Path(__file__).with_name("supported-licenses.json").open("rb") as license_file:
    SPDX_DATA = json.load(license_file)

legacy_path = Path(__file__).with_name("legacy-license-notices.json")
if legacy_path.is_file():
    with legacy_path.open("rb") as legacy_file:
        LEGACY_DATA = json.load(legacy_file)
else:
    LEGACY_DATA = {"licenses": {}}

SPDX_LICENSES = {item["licenseId"]: item for item in SPDX_DATA["licenses"]}
LEGACY_LICENSES = LEGACY_DATA.get("licenses", {})


class DiagnosticCode(StrEnum):
    MISSING_HEADER = "VPH001"
    OWNER_MISMATCH = "VPH002"
    INVALID_YEAR = "VPH003"
    STALE_YEAR = "VPH004"
    LICENSE_MISMATCH = "VPH005"
    INVALID_LAYOUT = "VPH006"
    DECODE_ERROR = "VPH007"
    UNSAFE_FIX = "VPH008"


@dataclass(frozen=True)
class Diagnostic:
    path: Path
    line: int
    column: int
    code: DiagnosticCode
    message: str
    fixable: bool = False


@dataclass(frozen=True)
class CommandError:
    message: str
    path: Path | None = None
    code: str = "VPH900"


@dataclass(frozen=True)
class CommandResult:
    command: str
    project_root: Path
    config_path: Path | None
    checked: int
    changed: tuple[Path, ...]
    diagnostics: tuple[Diagnostic, ...]
    expected_header: str | None
    error: CommandError | None = None

    @property
    def exit_code(self) -> int:
        if self.error is not None:
            return 2
        return 1 if self.diagnostics else 0


@dataclass(frozen=True)
class Settings:
    owner: str
    year: int
    license: str | None
    license_notice: str | None
    license_path: Path
    paths: tuple[str, ...]
    ignore_files: tuple[str, ...]
    ignore_folders: tuple[str, ...]
    project_root: Path
    config_path: Path | None


@dataclass(frozen=True)
class HeaderPolicy:
    owner: str
    starting_year: int
    current_year: int
    license_notices: tuple[str, ...]
    expected_header: str


@dataclass(frozen=True)
class FileIdentity:
    device: int
    inode: int
    mode: int
    links: int
    size: int
    mtime_ns: int
    attributes: int
    digest: str


@dataclass(frozen=True)
class ContentAnalysis:
    diagnostic: Diagnostic | None
    raw_source: bytes
    line_index: int | None = None
    old_years: bytes | None = None
    start_year: int | None = None


@dataclass(frozen=True)
class FileAnalysis:
    content: ContentAnalysis
    identity: FileIdentity | None
    unsafe_reason: str | None


class UnsafeRepairError(OSError):
    pass


def _normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _license_entries(license_id: str) -> list[dict]:
    entries = []
    legacy = LEGACY_LICENSES.get(license_id)
    if isinstance(legacy, dict):
        entries.append(legacy)
    current = SPDX_LICENSES.get(license_id)
    if isinstance(current, dict):
        entries.append({"name": current["name"], "urls": current["seeAlso"]})
    if not entries:
        raise ValueError(f"Invalid license identifier: {license_id}")
    return entries


def _license_notices(
    license_id: str | None,
    license_notice: str | None,
    license_path: Path,
) -> tuple[str, ...]:
    notices = []
    if license_id:
        if not license_path.is_file():
            raise FileNotFoundError("Unable to locate local copy of license text.")
        for entry in _license_entries(license_id):
            urls = entry["urls"] or [f"https://spdx.org/licenses/{license_id}.html"]
            for url in urls:
                notice = (
                    f"# This program is licensed under the {entry['name']}.\n"
                    f"# See LICENSE or go to <{url}> for full license details.\n"
                )
                if notice not in notices:
                    notices.append(notice)
    elif license_notice:
        notice_path = Path(license_notice)
        if not notice_path.is_file():
            raise FileNotFoundError("Unable to locate the text of the license notice.")
        notices.append(_normalize_newlines(notice_path.read_text(encoding="utf-8")))
    else:
        raise ValueError("One of the following args needs to be specified: 'license', 'license-notice'")
    return tuple(notices)


def build_policy(settings: Settings, current_year: int | None = None) -> HeaderPolicy:
    year = datetime.now().year if current_year is None else current_year
    if settings.year < 1000 or settings.year > year:
        raise ValueError(f"Invalid first copyright year: {settings.year}")
    if not settings.owner or "\n" in settings.owner or "\r" in settings.owner:
        raise ValueError("Please specify a single-line copyright owner")

    notices = _license_notices(settings.license, settings.license_notice, settings.license_path)
    years = f"{year}" if settings.year == year else f"<FILE_CREATION_YEAR>-{year}"
    expected = f"# Copyright (C) {years}, {settings.owner}.\n\n{notices[0]}"
    return HeaderPolicy(settings.owner, settings.year, year, notices, expected)


def get_header_options(
    owner: str,
    starting_year: int,
    license_id: str | None,
    license_notice: str | None,
    current_year: int | None = None,
    license_path: Path = Path("LICENSE"),
) -> list[list[str]]:
    settings = Settings(
        owner,
        starting_year,
        license_id,
        license_notice,
        license_path,
        (".",),
        (),
        (),
        Path.cwd(),
        None,
    )
    policy = build_policy(settings, current_year)
    year = policy.current_year
    years = [str(year), *(f"{start}-{year}" for start in range(starting_year, year))]
    options = [
        [f"# Copyright (C) {value}, {owner}.\n", BLANK_LINE, *notice.splitlines(keepends=True)]
        for value in years
        for notice in policy.license_notices
    ]
    options.append(policy.expected_header.splitlines(keepends=True))
    return options


def _is_link_or_reparse(file_stat: os.stat_result) -> bool:
    attributes = getattr(file_stat, "st_file_attributes", 0)
    return stat.S_ISLNK(file_stat.st_mode) or bool(attributes & REPARSE_POINT)


def _path_is_link_or_reparse(path: Path) -> bool:
    return _is_link_or_reparse(os.lstat(path))


def _raise_walk_error(error: OSError) -> None:
    raise error


def _walk_python_files(root: Path) -> list[Path]:
    candidates = []
    for directory, folder_names, file_names in os.walk(root, followlinks=False, onerror=_raise_walk_error):
        directory_path = Path(directory)
        folder_names[:] = [name for name in sorted(folder_names) if not _path_is_link_or_reparse(directory_path / name)]
        for name in sorted(file_names):
            candidate = directory_path / name
            if name.endswith(".py") and not _path_is_link_or_reparse(candidate):
                candidates.append(candidate)
    return candidates


def discover_files(paths: list[str] | tuple[str, ...], ignore_files, ignore_folders) -> list[Path]:
    if not paths:
        raise ValueError("Please specify at least one path to inspect")

    ignored_files = set(ignore_files)
    ignored_folders = {Path(folder) for folder in ignore_folders}
    source_paths = {}
    for raw_path in paths:
        path = Path(raw_path)
        if path.exists() and path.is_dir():
            if _path_is_link_or_reparse(path):
                raise ValueError(f"Refusing symlink or reparse-point directory: {raw_path}")
            candidates = _walk_python_files(path)
        elif path.is_file():
            candidates = [path]
        else:
            raise FileNotFoundError(f"Invalid path: {raw_path}")

        for source_path in candidates:
            if source_path.name in ignored_files or any(
                ignored_folder == source_path or ignored_folder in source_path.parents
                for ignored_folder in ignored_folders
            ):
                continue
            key = os.path.normcase(str(source_path.absolute()))
            source_paths.setdefault(key, source_path)
    return sorted(source_paths.values(), key=lambda item: item.as_posix())


def _decode_source(raw_source: bytes) -> str:
    encoding, _ = tokenize.detect_encoding(io.BytesIO(raw_source).readline)
    return raw_source.decode(encoding)


def _preamble(lines: list[str]) -> tuple[int, bool]:
    shebang = bool(lines and lines[0].startswith("#!"))
    cookie_index = None
    if lines and CODING_RE.match(lines[0]):
        cookie_index = 0
    elif len(lines) > 1 and COMMENT_OR_BLANK_RE.match(lines[0]) and CODING_RE.match(lines[1]):
        cookie_index = 1
    preamble_end = max(1 if shebang else 0, 0 if cookie_index is None else cookie_index + 1)
    if preamble_end == 0:
        return 0, True
    separator_valid = preamble_end < len(lines) and lines[preamble_end].rstrip("\r\n") == ""
    return preamble_end + 1 if separator_valid else preamble_end, separator_valid


def _diagnostic(
    path: Path,
    line: int,
    code: DiagnosticCode,
    message: str,
    fixable: bool = False,
) -> Diagnostic:
    return Diagnostic(path, max(line, 1), 1, code, message, fixable)


def _copyright_comments(source: str) -> tuple[list[int], list[tuple[int, re.Match[str]]]]:
    prefix_indices = []
    matches = []
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    try:
        for token in tokens:
            if token.type != tokenize.COMMENT:
                continue
            line_index = token.start[0] - 1
            if token.string.startswith("# Copyright"):
                prefix_indices.append(line_index)
            match = COPYRIGHT_RE.fullmatch(token.string)
            if match is not None:
                matches.append((line_index, match))
    except (IndentationError, tokenize.TokenError):
        pass
    return prefix_indices, matches


def _analyze_content(path: Path, raw_source: bytes, policy: HeaderPolicy) -> ContentAnalysis:
    try:
        source = _decode_source(raw_source)
    except (LookupError, SyntaxError, UnicodeDecodeError) as error:
        return ContentAnalysis(
            _diagnostic(path, 1, DiagnosticCode.DECODE_ERROR, f"unable to decode Python source: {error}"),
            raw_source,
        )

    lines = source.splitlines(keepends=True)
    header_index, separator_valid = _preamble(lines)
    prefix_indices, matches = _copyright_comments(source)

    if header_index >= len(lines) or not prefix_indices:
        return ContentAnalysis(
            _diagnostic(path, header_index + 1, DiagnosticCode.MISSING_HEADER, "missing legal header"), raw_source
        )
    if not separator_valid or len(prefix_indices) != 1 or len(matches) != 1 or matches[0][0] != header_index:
        line = prefix_indices[0] + 1
        return ContentAnalysis(
            _diagnostic(path, line, DiagnosticCode.INVALID_LAYOUT, "malformed, misplaced, or ambiguous header"),
            raw_source,
        )

    line_index, match = matches[0]
    if match.group("owner") != policy.owner:
        return ContentAnalysis(
            _diagnostic(
                path,
                line_index + 1,
                DiagnosticCode.OWNER_MISMATCH,
                f"copyright owner is '{match.group('owner')}'; expected '{policy.owner}'",
            ),
            raw_source,
        )

    start_year = int(match.group("start"))
    end_year = int(match.group("end")) if match.group("end") else None
    if (
        start_year < policy.starting_year
        or start_year > policy.current_year
        or (end_year is not None and (end_year < start_year or end_year > policy.current_year))
    ):
        return ContentAnalysis(
            _diagnostic(
                path,
                line_index + 1,
                DiagnosticCode.INVALID_YEAR,
                f"copyright year '{match.group('years')}' is outside the accepted range",
            ),
            raw_source,
        )

    blank_index = line_index + 1
    if blank_index >= len(lines) or lines[blank_index].rstrip("\r\n") != "":
        return ContentAnalysis(
            _diagnostic(
                path,
                blank_index + 1,
                DiagnosticCode.INVALID_LAYOUT,
                "expected one blank line between copyright and license notice",
            ),
            raw_source,
        )

    notice_source = _normalize_newlines("".join(lines[blank_index + 1 :]))
    if not any(notice_source.startswith(notice) for notice in policy.license_notices):
        return ContentAnalysis(
            _diagnostic(
                path,
                blank_index + 2,
                DiagnosticCode.LICENSE_MISMATCH,
                "missing or mismatched license notice",
            ),
            raw_source,
        )

    stale = end_year < policy.current_year if end_year is not None else start_year < policy.current_year
    if stale:
        return ContentAnalysis(
            _diagnostic(
                path,
                line_index + 1,
                DiagnosticCode.STALE_YEAR,
                f"copyright year ends at {end_year or start_year}; expected {policy.current_year}",
            ),
            raw_source,
            line_index,
            match.group("years").encode("ascii"),
            start_year,
        )
    return ContentAnalysis(None, raw_source)


def is_valid_header(raw_source: bytes, header_options: list[list[str]]) -> bool:
    try:
        source = _normalize_newlines(_decode_source(raw_source))
    except (LookupError, SyntaxError, UnicodeDecodeError):
        return False
    lines = source.splitlines(keepends=True)
    header_index, _ = _preamble(lines)
    source = "".join(lines[header_index:])
    # The last option is the display-only template containing <FILE_CREATION_YEAR>.
    return any(source.startswith("".join(option)) for option in header_options[:-1])


def _attributes(file_stat: os.stat_result) -> int:
    return getattr(file_stat, "st_file_attributes", 0)


def _identity(file_stat: os.stat_result, raw_source: bytes) -> FileIdentity:
    return FileIdentity(
        file_stat.st_dev,
        file_stat.st_ino,
        file_stat.st_mode,
        file_stat.st_nlink,
        file_stat.st_size,
        file_stat.st_mtime_ns,
        _attributes(file_stat),
        hashlib.sha256(raw_source).hexdigest(),
    )


def _unsafe_reason(path: Path, before: os.stat_result, after: os.stat_result, project_root: Path) -> str | None:
    if _is_link_or_reparse(after):
        return "repair target is a symlink or reparse point"
    if not stat.S_ISREG(after.st_mode):
        return "repair target is not a regular file"
    if after.st_nlink != 1:
        return f"repair target has {after.st_nlink} hard links"
    parents = []
    parent = path.absolute().parent
    stop = project_root.absolute().parent
    while parent != stop and parent != parent.parent:
        parents.append(parent)
        parent = parent.parent
    if any(_path_is_link_or_reparse(item) for item in parents):
        return "repair target traverses a symlink or reparse-point parent"
    if (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_nlink,
        before.st_size,
        before.st_mtime_ns,
        _attributes(before),
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_nlink,
        after.st_size,
        after.st_mtime_ns,
        _attributes(after),
    ):
        return "repair target changed while it was read"
    return None


def analyze_file(path: Path, policy: HeaderPolicy, project_root: Path) -> FileAnalysis:
    before = os.lstat(path)
    raw_source = path.read_bytes()
    after = os.lstat(path)
    content = _analyze_content(path, raw_source, policy)
    reason = _unsafe_reason(path, before, after, project_root)
    identity = None if reason is not None else _identity(after, raw_source)
    if content.diagnostic is not None and content.diagnostic.code == DiagnosticCode.STALE_YEAR:
        content = replace(content, diagnostic=replace(content.diagnostic, fixable=identity is not None))
    return FileAnalysis(content, identity, reason)


def _matches_identity(path: Path, identity: FileIdentity) -> bool:
    current_stat = os.lstat(path)
    if _is_link_or_reparse(current_stat) or not stat.S_ISREG(current_stat.st_mode):
        return False
    current = _identity(current_stat, path.read_bytes())
    return current == identity


def _atomic_write(path: Path, content: bytes, identity: FileIdentity) -> None:
    if not _matches_identity(path, identity):
        raise UnsafeRepairError("repair target changed before writing")
    file_descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        temporary_path.chmod(stat.S_IMODE(identity.mode))
        if not _matches_identity(path, identity):
            raise UnsafeRepairError("repair target changed before replacement")
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def repair_header(path: Path, analysis: FileAnalysis, policy: HeaderPolicy) -> None:
    content = analysis.content
    if (
        content.diagnostic is None
        or content.diagnostic.code != DiagnosticCode.STALE_YEAR
        or content.line_index is None
        or content.old_years is None
        or content.start_year is None
    ):
        raise ValueError("Header is not a recognized stale-year repair")
    if analysis.identity is None:
        raise UnsafeRepairError(analysis.unsafe_reason or "repair target is unsafe")

    raw_lines = content.raw_source.splitlines(keepends=True)
    raw_line = raw_lines[content.line_index]
    prefix = b"# Copyright (C) "
    needle = prefix + content.old_years + b", "
    if raw_line.count(needle) != 1:
        raise UnsafeRepairError("copyright bytes changed before repair")
    year_start = raw_line.index(needle) + len(prefix)
    replacement = f"{content.start_year}-{policy.current_year}".encode("ascii")
    raw_lines[content.line_index] = (
        raw_line[:year_start] + replacement + raw_line[year_start + len(content.old_years) :]
    )
    repaired_source = b"".join(raw_lines)
    if _analyze_content(path, repaired_source, policy).diagnostic is not None:
        raise UnsafeRepairError("repaired bytes do not satisfy the configured policy")
    _atomic_write(path, repaired_source, analysis.identity)


def _unsafe_diagnostic(analysis: FileAnalysis) -> Diagnostic:
    diagnostic = analysis.content.diagnostic
    if diagnostic is None:
        raise ValueError("Expected a stale-year diagnostic")
    return replace(
        diagnostic,
        code=DiagnosticCode.UNSAFE_FIX,
        message=analysis.unsafe_reason or "repair target changed before replacement",
        fixable=False,
    )


def _error_result(
    settings: Settings,
    command: str,
    expected_header: str | None,
    checked: int,
    changed: list[Path],
    diagnostics: list[Diagnostic],
    error: Exception,
    path: Path | None = None,
) -> CommandResult:
    return CommandResult(
        command,
        settings.project_root,
        settings.config_path,
        checked,
        tuple(sorted(changed, key=lambda item: item.as_posix())),
        tuple(diagnostics),
        expected_header,
        CommandError(str(error), path),
    )


def run(settings: Settings, command: str, current_year: int | None = None) -> CommandResult:
    if command not in {"check", "fix"}:
        raise ValueError(f"Invalid command '{command}': expected 'check' or 'fix'")
    policy = build_policy(settings, current_year)
    try:
        source_paths = discover_files(settings.paths, settings.ignore_files, settings.ignore_folders)
    except (OSError, ValueError) as error:
        return _error_result(settings, command, policy.expected_header, 0, [], [], error)
    analyses = []
    for path in source_paths:
        try:
            analyses.append((path, analyze_file(path, policy, settings.project_root)))
        except OSError as error:
            diagnostics = [item.content.diagnostic for _, item in analyses if item.content.diagnostic]
            return _error_result(
                settings,
                command,
                policy.expected_header,
                len(analyses),
                [],
                diagnostics,
                error,
                path,
            )

    if command == "check":
        diagnostics = tuple(item.content.diagnostic for _, item in analyses if item.content.diagnostic)
        return CommandResult(
            command,
            settings.project_root,
            settings.config_path,
            len(source_paths),
            (),
            diagnostics,
            policy.expected_header,
        )

    changed = []
    unsafe = {}
    for path, analysis in analyses:
        diagnostic = analysis.content.diagnostic
        if diagnostic is None or diagnostic.code != DiagnosticCode.STALE_YEAR:
            continue
        if analysis.identity is None:
            unsafe[path] = _unsafe_diagnostic(analysis)
            continue
        try:
            repair_header(path, analysis, policy)
            changed.append(path)
        except UnsafeRepairError as error:
            unsafe[path] = replace(
                diagnostic,
                code=DiagnosticCode.UNSAFE_FIX,
                message=str(error),
                fixable=False,
            )
        except OSError as error:
            remaining = []
            for item_path, item in analyses:
                item_diagnostic = unsafe.get(item_path, item.content.diagnostic)
                if item_path not in changed and item_diagnostic is not None:
                    remaining.append(item_diagnostic)
            return _error_result(
                settings,
                command,
                policy.expected_header,
                len(source_paths),
                changed,
                remaining,
                error,
                path,
            )

    diagnostics = []
    for path in source_paths:
        if path in unsafe:
            diagnostics.append(unsafe[path])
            continue
        try:
            analysis = analyze_file(path, policy, settings.project_root)
        except OSError as error:
            return _error_result(
                settings,
                command,
                policy.expected_header,
                len(source_paths),
                changed,
                diagnostics,
                error,
                path,
            )
        if analysis.content.diagnostic is not None:
            diagnostics.append(analysis.content.diagnostic)
    return CommandResult(
        command,
        settings.project_root,
        settings.config_path,
        len(source_paths),
        tuple(sorted(changed, key=lambda item: item.as_posix())),
        tuple(diagnostics),
        policy.expected_header,
    )
