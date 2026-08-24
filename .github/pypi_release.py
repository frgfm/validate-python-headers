# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

import argparse
import hashlib
import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed uv executable
import time
import urllib.error
import urllib.request
from pathlib import Path


def artifact_hashes(directory: Path) -> dict[str, str]:
    artifacts = sorted([*directory.glob("*.whl"), *directory.glob("*.tar.gz")])
    if len(artifacts) != 2:
        raise ValueError(f"Expected one wheel and one sdist, found {len(artifacts)}")
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in artifacts}


def published_hashes(package: str, version: str) -> dict[str, str]:
    url = f"https://pypi.org/pypi/{package}/{version}/json"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return {}
        raise
    return {item["filename"]: item["digests"]["sha256"] for item in payload["urls"]}


def reject_unexpected(expected: dict[str, str], remote: dict[str, str]) -> None:
    unexpected = remote.keys() - expected.keys()
    if unexpected:
        raise ValueError(f"Published unexpected artifacts: {', '.join(sorted(unexpected))}")


def publish(directory: Path, package: str, version: str) -> None:
    expected = artifact_hashes(directory)
    remote = published_hashes(package, version)
    reject_unexpected(expected, remote)
    mismatched = {name for name, digest in expected.items() if name in remote and remote[name] != digest}
    if mismatched:
        raise ValueError(f"Published hash mismatch for {', '.join(sorted(mismatched))}")
    missing = [directory / name for name in expected if name not in remote]
    if not missing:
        return
    uv = shutil.which("uv")
    if uv is None:
        raise FileNotFoundError("uv is required to publish distributions")
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - fixed uv and local artifacts
        [uv, "publish", "--trusted-publishing", "always", *map(str, missing)], check=True
    )


def verify(directory: Path, package: str, version: str, attempts: int, delay: int) -> None:
    expected = artifact_hashes(directory)
    for attempt in range(attempts):
        remote = published_hashes(package, version)
        reject_unexpected(expected, remote)
        mismatched = {
            name: (digest, remote.get(name)) for name, digest in expected.items() if remote.get(name) != digest
        }
        if not mismatched:
            return
        if attempt + 1 < attempts:
            time.sleep(delay)
    raise ValueError(f"Published artifacts did not converge: {mismatched}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish or verify byte-identical PyPI artifacts")
    parser.add_argument("command", choices=("publish", "verify"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--package", default="validate-python-headers")
    parser.add_argument("--version", required=True)
    parser.add_argument("--attempts", type=int, default=12)
    parser.add_argument("--delay", type=int, default=10)
    args = parser.parse_args()
    if args.command == "publish":
        publish(args.directory, args.package, args.version)
    else:
        verify(args.directory, args.package, args.version, args.attempts, args.delay)


if __name__ == "__main__":
    main()
