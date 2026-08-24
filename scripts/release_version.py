# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

TAG_RE = re.compile(r"v\d+\.\d+\.\d+(?:rc\d+)?")


def release_version(tag: str, pyproject: Path = Path("pyproject.toml")) -> str:
    if TAG_RE.fullmatch(tag) is None:
        raise ValueError(f"Unsupported release tag: {tag}")
    with pyproject.open("rb") as stream:
        version = tomllib.load(stream)["project"]["version"]
    if tag != f"v{version}":
        raise ValueError(f"Release tag {tag} does not match package version {version}")
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description="Require an exact release tag/package version match")
    parser.add_argument("tag")
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    args = parser.parse_args()
    sys.stdout.write(release_version(args.tag, args.pyproject) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
