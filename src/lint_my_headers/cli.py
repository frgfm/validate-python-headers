# Copyright (C) 2022-2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

"""Python invocation shim; all linting and argument parsing run in Rust."""

import importlib.metadata
import subprocess  # ruff: ignore[suspicious-subprocess-import] - installed native executable
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    distribution = importlib.metadata.distribution("lint-my-headers")
    name = "lmh.exe" if sys.platform == "win32" else "lmh"
    for entry in distribution.files or ():
        if entry.name == name:
            executable = Path(str(distribution.locate_file(entry)))
            if executable.is_file():
                try:
                    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
                        [str(executable), *(sys.argv[1:] if argv is None else argv)], check=False
                    ).returncode
                except KeyboardInterrupt:
                    return 2
    raise FileNotFoundError("The installed lint-my-headers distribution is missing its lmh executable")
