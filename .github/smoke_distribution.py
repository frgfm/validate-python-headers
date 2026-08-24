# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

import importlib.metadata
import importlib.resources
import json
import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed local executables
import sys
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

PACKAGE = "lint-my-headers"


def fail(message: str) -> None:
    raise RuntimeError(message)


def run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - fixed executable paths
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def require_command(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        fail(f"Missing installed command: {name}")
    return executable


def verify_version(command: list[str], expected: str) -> None:
    result = run([*command, "--version"])
    if result.returncode != 0 or not result.stdout.rstrip().endswith(expected):
        fail(f"Version smoke failed for {' '.join(command)}: {result.stdout}{result.stderr}")


def main() -> int:
    expected = os.environ.get("EXPECTED_VERSION")
    if not expected:
        fail("EXPECTED_VERSION is required")
    installed = importlib.metadata.version(PACKAGE)
    if installed != expected:
        fail(f"Installed version mismatch: expected {expected}, got {installed}")
    commands = {
        entry.name
        for entry in importlib.metadata.distribution(PACKAGE).entry_points
        if entry.group == "console_scripts"
    }
    if commands != {"lmh", "lint-my-headers"}:
        fail(f"Unexpected console commands: {commands}")
    if any(path.parts[0] == "tests" for path in importlib.metadata.files(PACKAGE) or ()):
        fail("Distribution unexpectedly contains the test suite")

    verify_version([require_command("lmh")], expected)
    verify_version([require_command("lint-my-headers")], expected)
    verify_version([sys.executable, "-m", "lint_my_headers"], expected)

    package_files = importlib.resources.files("lint_my_headers")
    for name in ("supported-licenses.json", "legacy-license-notices.json"):
        if not package_files.joinpath(name).is_file():
            fail(f"Missing package data: {name}")

    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        root.joinpath("LICENSE").write_text("Apache-2.0\n", encoding="utf-8")
        root.joinpath("pyproject.toml").write_text(
            """[tool.lint-my-headers]
owner = "Example Owner"
starting-year = 2022
license = "Apache-2.0"
paths = ["src"]
ignore-files = []
ignore-folders = []
""",
            encoding="utf-8",
        )
        source = root / "src/example.py"
        source.parent.mkdir()
        year = datetime.now().year
        source.write_text(
            f"""# Copyright (C) {year}, Example Owner.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

value = 1
""",
            encoding="utf-8",
        )
        result = run([require_command("lmh"), "check", "--output-format", "json"], root)
        if result.returncode != 0:
            fail(f"Installed check failed: {result.stdout}{result.stderr}")
        payload = json.loads(result.stdout)
        if payload["checked"] != 1 or payload["diagnostics"] or payload["error"] is not None:
            fail(f"Unexpected installed check result: {payload}")
        stale = source.read_bytes().replace(str(year).encode(), str(year - 1).encode(), 1)
        source.write_bytes(stale)
        result = run([require_command("lmh"), "fix", "--output-format", "json"], root)
        if result.returncode != 0 or json.loads(result.stdout)["changed"] != ["src/example.py"]:
            fail(f"Installed fix failed: {result.stdout}{result.stderr}")
        repaired = stale.replace(str(year - 1).encode(), f"{year - 1}-{year}".encode(), 1)
        if source.read_bytes() != repaired:
            fail("Installed fix changed unexpected bytes")

    sys.stdout.write(f"Distribution smoke passed for {PACKAGE} {expected}.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
