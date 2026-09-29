# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

import argparse
import hashlib
import json
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed uv executable
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path


def verify_versions(root: Path) -> None:
    python_version = tomllib.loads(root.joinpath("pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    rust_version = tomllib.loads(root.joinpath("Cargo.toml").read_text(encoding="utf-8"))["package"]["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+(rc\d+)?", python_version):
        raise ValueError(f"Unsupported release version: {python_version}")
    if rust_version.replace("-rc.", "rc") != python_version:
        raise ValueError(f"Cargo version {rust_version} does not match package version {python_version}")


def artifact_hashes(directory: Path) -> dict[str, str]:
    wheels = sorted(directory.glob("*.whl"))
    sources = list(directory.glob("*.tar.gz"))
    if not wheels or len(sources) != 1:
        raise ValueError(
            f"Expected platform wheels and one sdist, found {len(wheels)} wheels and {len(sources)} sdists"
        )
    artifacts = sorted([*wheels, *sources])
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
    parser.add_argument("command", choices=("publish", "verify", "versions"))
    parser.add_argument("directory", type=Path, nargs="?")
    parser.add_argument("--package", default="lint-my-headers")
    parser.add_argument("--version")
    parser.add_argument("--attempts", type=int, default=12)
    parser.add_argument("--delay", type=int, default=10)
    args = parser.parse_args()
    if args.command == "versions":
        verify_versions(Path.cwd())
    elif args.directory is None or args.version is None:
        parser.error("publish and verify require a directory and --version")
    elif args.command == "publish":
        publish(args.directory, args.package, args.version)
    else:
        verify(args.directory, args.package, args.version, args.attempts, args.delay)


if __name__ == "__main__":
    main()
