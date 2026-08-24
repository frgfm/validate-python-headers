# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

from __future__ import annotations

import importlib.resources
import json
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed local executables and arguments.
import sys
from datetime import datetime
from importlib import metadata
from pathlib import Path
from tempfile import TemporaryDirectory

PACKAGE = "lint-my-headers"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def command(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - fixed smoke commands.
        args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed ({result.returncode}): {result.stdout}{result.stderr}")
    return result


def main() -> int:
    distribution = metadata.distribution(PACKAGE)
    require(distribution.metadata["Name"] == PACKAGE, "unexpected distribution name")
    scripts = {
        entry.name
        for entry in distribution.entry_points
        if entry.group == "console_scripts" and entry.dist.name == PACKAGE
    }
    require(scripts == {"lmh", "lint-my-headers"}, f"unexpected console scripts: {sorted(scripts)}")
    require("vph" not in scripts and "validate-python-headers" not in scripts, "legacy console script leaked")
    require(
        importlib.resources.files("lint_my_headers").joinpath("supported-licenses.json").is_file(),
        "license data missing",
    )
    require(
        importlib.resources.files("lint_my_headers").joinpath("supported-license-compatibility.json").is_file(),
        "license compatibility data missing",
    )

    current_year = datetime.now().year
    start_year = current_year - 2
    notice = (
        "# This program is licensed under the Apache License 2.0.\n"
        "# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.\n"
    )
    with TemporaryDirectory() as directory:
        root = Path(directory)
        root.joinpath("LICENSE").write_text("Apache-2.0\n", encoding="utf-8")
        root.joinpath("pyproject.toml").write_text(
            f"""[tool.lint-my-headers]
owner = "Example Owner"
starting-year = {start_year}
license = "Apache-2.0"
paths = ["src"]
ignore-files = []
ignore-folders = []
""",
            encoding="utf-8",
        )
        source = root / "src/example.py"
        source.parent.mkdir()
        source.write_text(
            f"# Copyright (C) {start_year}, Example Owner.\n\n{notice}\nvalue = 1\n",
            encoding="utf-8",
        )
        payload = json.loads(command("lmh", "fix", "--output-format", "json", cwd=root).stdout)
        require(payload["changed"] == ["src/example.py"], "fix did not report the changed file")
        require(payload["diagnostics"] == [] and payload["error"] is None, "fix left an unexpected problem")
        require(f"{start_year}-{current_year}" in source.read_text(encoding="utf-8"), "fix did not update the year")
        check = json.loads(command("lint-my-headers", "check", "--output-format", "json", cwd=root).stdout)
        require(check["diagnostics"] == [] and check["checked"] == 1, "long command check failed")

    version = distribution.version
    require(version in command("lmh", "--version").stdout, "short command version mismatch")
    require(version in command(sys.executable, "-m", "lint_my_headers", "--version").stdout, "module version mismatch")
    sys.stdout.write(f"smoke passed for {PACKAGE} {version}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
