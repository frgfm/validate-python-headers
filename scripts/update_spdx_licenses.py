# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed git executable and arguments.
import urllib.request
from pathlib import Path

BASELINE_SHA256 = "d557d74124ce6b367efd161e7b53ab1743ad45e302c3476bfb0988ee67b766e0"
DEFAULT_BASELINE = "94972478"
DEFAULT_SPDX_TAG = "v3.28.0"
DEFAULT_UPSTREAM_SHA256 = "f728c534d8bd1044fc515a2ddb2292be99559021d830bfa3281be0bcd36302ee"
TAG_RE = re.compile(r"v\d+\.\d+\.\d+")


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _baseline(ref: str, root: Path) -> bytes:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required to read the compatibility baseline")
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - fixed git command.
        [git, "show", f"{ref}:src/validate_headers/supported-licenses.json"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
    )
    if _sha256(result.stdout) != BASELINE_SHA256:
        raise ValueError(f"Unexpected SPDX baseline bytes at {ref}")
    return result.stdout


def _upstream(tag: str, expected_sha256: str) -> bytes:
    if TAG_RE.fullmatch(tag) is None:
        raise ValueError(f"Invalid SPDX tag: {tag}")
    url = f"https://raw.githubusercontent.com/spdx/license-list-data/{tag}/json/licenses.json"
    with urllib.request.urlopen(url, timeout=30) as response:
        content = response.read()
    actual = _sha256(content)
    if actual != expected_sha256:
        raise ValueError(f"Unexpected SPDX snapshot checksum: {actual}")
    return content


def _compatibility(baseline: bytes, upstream: bytes) -> bytes:
    old_items = {item["licenseId"]: item for item in json.loads(baseline)["licenses"]}
    new_items = {item["licenseId"]: item for item in json.loads(upstream)["licenses"]}
    compatibility = {}
    for identifier, old in sorted(old_items.items()):
        new = new_items.get(identifier)
        old_urls = sorted(old["seeAlso"])
        if new is None or old["name"] != new["name"] or old_urls != sorted(new["seeAlso"]):
            compatibility[identifier] = {"name": old["name"], "urls": old_urls}
    return (json.dumps(compatibility, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh the pinned SPDX license snapshot and compatibility data")
    parser.add_argument("--baseline-ref", default=DEFAULT_BASELINE)
    parser.add_argument("--spdx-tag", default=DEFAULT_SPDX_TAG)
    parser.add_argument("--expected-sha256", default=DEFAULT_UPSTREAM_SHA256)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    baseline = _baseline(args.baseline_ref, root)
    upstream = _upstream(args.spdx_tag, args.expected_sha256)
    compatibility = _compatibility(baseline, upstream)
    targets = {
        root / "src/lint_my_headers/supported-licenses.json": upstream,
        root / "src/lint_my_headers/supported-license-compatibility.json": compatibility,
    }
    if args.check:
        mismatches = [
            str(path.relative_to(root))
            for path, content in targets.items()
            if not path.is_file() or path.read_bytes() != content
        ]
        if mismatches:
            raise SystemExit("SPDX generated files are stale: " + ", ".join(mismatches))
        return 0
    for path, content in targets.items():
        path.write_bytes(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
