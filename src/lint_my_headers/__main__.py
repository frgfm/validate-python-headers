# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

import os
import sys

from .cli import _find_binary, main

if sys.platform == "win32":
    raise SystemExit(main())

executable = str(_find_binary())
# Absolute installed executable and literal argv; no shell or PATH lookup.
os.execv(executable, [executable, *sys.argv[1:]])  # nosec B606 # ruff: ignore[start-process-with-no-shell]
