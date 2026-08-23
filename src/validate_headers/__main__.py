# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

import sys
from importlib import import_module
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
main = import_module("validate_headers.cli").main

raise SystemExit(main())
