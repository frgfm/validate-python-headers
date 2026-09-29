# Copyright (C) 2022-2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

"""Python invocation shim; all linting and argument parsing run in Rust."""

import importlib.metadata
import sys
from pathlib import Path


def _find_binary() -> Path:
    distribution = importlib.metadata.distribution("lint-my-headers")
    name = "lmh.exe" if sys.platform == "win32" else "lmh"
    for entry in distribution.files or ():
        if entry.name == name:
            executable = Path(str(distribution.locate_file(entry))).absolute()
            if executable.is_file():
                return executable
    raise FileNotFoundError("The installed lint-my-headers distribution is missing its lmh executable")


def main(argv: list[str] | None = None) -> int:
    import subprocess  # ruff: ignore[suspicious-subprocess-import] - installed native executable

    try:
        return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [str(_find_binary()), *(sys.argv[1:] if argv is None else argv)], check=False
        ).returncode
    except KeyboardInterrupt:
        return 2
