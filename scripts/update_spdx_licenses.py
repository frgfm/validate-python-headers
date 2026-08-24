# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

import argparse
import hashlib
import json
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed git executable
import sys
import urllib.request
from pathlib import Path

SNAPSHOT_PATH = Path("src/validate_headers/supported-licenses.json")
COMPATIBILITY_PATH = Path("src/validate_headers/legacy-license-notices.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the vendored SPDX license list without breaking old notices")
    parser.add_argument("--baseline-ref", required=True, help="git commit containing the previous SPDX snapshot")
    parser.add_argument("--baseline-sha256", required=True, help="expected SHA-256 of the previous snapshot")
    parser.add_argument("--spdx-tag", required=True, help="spdx/license-list-data tag, for example v3.28.0")
    parser.add_argument("--expected-sha256", required=True, help="expected SHA-256 of the downloaded snapshot")
    parser.add_argument("--check", action="store_true", help="verify tracked outputs without changing them")
    return parser.parse_args()


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def load_baseline(reference: str) -> bytes:
    if re.fullmatch(r"[0-9a-f]{7,40}", reference) is None:
        raise ValueError("baseline ref must be a hexadecimal commit ID")
    git = shutil.which("git")
    if git is None:
        raise FileNotFoundError("git is required to read the baseline snapshot")
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - validated revision
        [git, "show", f"{reference}:{SNAPSHOT_PATH.as_posix()}"],
        check=True,
        capture_output=True,
    )
    return result.stdout


def fetch_snapshot(tag: str) -> tuple[str, bytes]:
    url = f"https://raw.githubusercontent.com/spdx/license-list-data/{tag}/json/licenses.json"
    with urllib.request.urlopen(url, timeout=30) as response:
        return url, response.read()


def compatibility_bytes(baseline: bytes, current: bytes, baseline_ref: str, source_url: str) -> bytes:
    previous_data = json.loads(baseline)
    current_data = json.loads(current)
    current_licenses = {item["licenseId"]: item for item in current_data["licenses"]}
    compatibility = {}
    for previous in previous_data["licenses"]:
        current_license = current_licenses.get(previous["licenseId"])
        if current_license is None or (
            previous["name"] != current_license["name"] or previous["seeAlso"] != current_license["seeAlso"]
        ):
            compatibility[previous["licenseId"]] = {
                "name": previous["name"],
                "urls": previous["seeAlso"],
            }
    payload = {
        "baseline_ref": baseline_ref,
        "baseline_version": previous_data["licenseListVersion"],
        "current_source": source_url,
        "current_version": current_data["licenseListVersion"],
        "licenses": compatibility,
    }
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def verify_digest(label: str, content: bytes, expected: str) -> None:
    actual = sha256(content)
    if actual != expected:
        raise ValueError(f"{label} SHA-256 mismatch: expected {expected}, got {actual}")


def main() -> int:
    args = parse_args()
    baseline = load_baseline(args.baseline_ref)
    verify_digest("baseline", baseline, args.baseline_sha256)
    source_url, snapshot = fetch_snapshot(args.spdx_tag)
    verify_digest("download", snapshot, args.expected_sha256)
    compatibility = compatibility_bytes(baseline, snapshot, args.baseline_ref, source_url)

    outputs = {SNAPSHOT_PATH: snapshot, COMPATIBILITY_PATH: compatibility}
    if args.check:
        stale = [path for path, expected in outputs.items() if not path.is_file() or path.read_bytes() != expected]
        if stale:
            sys.stderr.write("SPDX outputs are stale:\n" + "\n".join(f"- {path}" for path in stale) + "\n")
            return 1
        return 0

    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    sys.stdout.write(
        f"Updated SPDX {json.loads(snapshot)['licenseListVersion']} with "
        f"{len(json.loads(compatibility)['licenses'])} compatibility entries.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
