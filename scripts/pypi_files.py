# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT = "lint-my-headers"


def _remote_files(version: str) -> dict[str, str] | None:
    url = f"https://pypi.org/pypi/{PROJECT}/{version}/json"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            document = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
    return {item["filename"]: item["digests"]["sha256"] for item in document["urls"]}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _compare(version: str, paths: list[Path]) -> list[Path]:
    remote = _remote_files(version)
    if remote is None:
        return paths
    missing = []
    for path in paths:
        actual = _digest(path)
        expected = remote.get(path.name)
        if expected is None:
            missing.append(path)
        elif expected != actual:
            raise RuntimeError(f"PyPI hash mismatch for {path.name}: local {actual}, remote {expected}")
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Select missing PyPI files and fail on hash mismatches")
    parser.add_argument("--version", required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    if args.retries < 1:
        raise ValueError("--retries must be positive")

    missing = args.files
    for attempt in range(args.retries):
        missing = _compare(args.version, args.files)
        if not missing or not args.verify:
            break
        if attempt + 1 < args.retries:
            time.sleep(5)
    if args.verify:
        if missing:
            raise SystemExit("PyPI is missing: " + ", ".join(path.name for path in missing))
        return 0
    for path in missing:
        sys.stdout.write(f"{path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
