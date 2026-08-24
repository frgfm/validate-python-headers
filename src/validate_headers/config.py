# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import cast

from .core import Settings

CONFIG_SECTION = "[tool.validate-python-headers]"
CONFIG_KEYS = {"owner", "starting-year", "license", "license-notice", "paths", "ignore-files", "ignore-folders"}


def _find_pyproject(config_path: str | None) -> Path | None:
    if config_path is not None:
        path = Path(config_path)
        if not path.is_file():
            raise FileNotFoundError(f"Invalid configuration path: {config_path}")
        return path.resolve()

    for directory in (Path.cwd(), *Path.cwd().parents):
        candidate = directory / "pyproject.toml"
        if candidate.is_file():
            return candidate.resolve()
    return None


def _configuration_table(document: dict[str, object], path: Path) -> dict[str, object]:
    tool_config = document.get("tool", {})
    if not isinstance(tool_config, dict):
        raise ValueError(f"Invalid [tool]: expected a table in {path}")
    config = tool_config.get("validate-python-headers", {})
    if not isinstance(config, dict):
        raise ValueError(f"Invalid {CONFIG_SECTION}: expected a table in {path}")

    unknown_keys = sorted(set(config) - CONFIG_KEYS)
    if unknown_keys:
        raise ValueError(f"Invalid {CONFIG_SECTION}.{unknown_keys[0]}: unknown key in {path}")
    return config


def _validate_scalar_configuration(config: dict[str, object], path: Path) -> None:
    for key in ("owner", "license", "license-notice"):
        if key in config and (not isinstance(config[key], str) or not config[key]):
            raise ValueError(f"Invalid {CONFIG_SECTION}.{key}: expected a non-empty string in {path}")
    if "starting-year" in config and (
        not isinstance(config["starting-year"], int)
        or isinstance(config["starting-year"], bool)
        or config["starting-year"] < 1000
    ):
        raise ValueError(f"Invalid {CONFIG_SECTION}.starting-year: expected a four-digit integer in {path}")


def _validate_list_configuration(config: dict[str, object], path: Path) -> None:
    for key in ("paths", "ignore-files", "ignore-folders"):
        if key not in config:
            continue
        value = config[key]
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            raise ValueError(f"Invalid {CONFIG_SECTION}.{key}: expected an array of non-empty strings in {path}")
    if "paths" in config and not config["paths"]:
        raise ValueError(f"Invalid {CONFIG_SECTION}.paths: expected at least one path in {path}")


def load_configuration(config_path: str | None = None) -> tuple[dict[str, object], Path, Path | None]:
    path = _find_pyproject(config_path)
    if path is None:
        return {}, Path.cwd().resolve(), None

    with path.open("rb") as config_file:
        document = tomllib.load(config_file)
    config = _configuration_table(document, path)
    _validate_scalar_configuration(config, path)
    _validate_list_configuration(config, path)
    return config, path.parent, path


def _split_values(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _relative_path(path: Path) -> str:
    return Path(os.path.relpath(path, Path.cwd())).as_posix()


def resolve_args(args) -> Settings:
    config, project_root, config_path = load_configuration(args.config)
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
            license_notice = _relative_path(project_root / license_notice)
    if bool(license_id) == bool(license_notice):
        raise ValueError(
            f"Configure exactly one of {CONFIG_SECTION}.license or {CONFIG_SECTION}.license-notice, "
            "or pass one matching CLI option"
        )

    if args.paths and args.folders is not None:
        raise ValueError("Pass explicit paths or --folders, not both")
    if args.paths:
        paths = tuple(args.paths)
    elif args.folders is not None:
        paths = _split_values(args.folders)
    else:
        configured_paths = cast(list[str], config.get("paths", ["."]))
        paths = tuple(_relative_path(project_root / path) for path in configured_paths)

    ignore_files = (
        _split_values(args.ignore_files)
        if args.ignore_files is not None
        else tuple(cast(list[str], config.get("ignore-files", ["__init__.py"])))
    )
    configured_ignore_folders = cast(list[str], config.get("ignore-folders", [".github"]))
    ignore_folders = (
        _split_values(args.ignore_folders)
        if args.ignore_folders is not None
        else tuple(_relative_path(project_root / folder) for folder in configured_ignore_folders)
    )
    if not paths:
        raise ValueError(f"Invalid {CONFIG_SECTION}.paths: expected at least one path")

    return Settings(
        owner,
        year,
        license_id if isinstance(license_id, str) else None,
        license_notice if isinstance(license_notice, str) else None,
        project_root / "LICENSE",
        paths,
        ignore_files,
        ignore_folders,
        project_root,
        config_path,
    )
