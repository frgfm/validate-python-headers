# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

import shutil
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    source = root / "site"
    target = root / ".docs-site"
    if not (source / "index.html").is_file():
        raise FileNotFoundError("Build documentation with make docs before preparing Cloudflare assets.")
    if source.is_symlink() or target.is_symlink():
        raise ValueError("Documentation build directories must not be symlinks.")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target / "lint-my-headers")
    print("Prepared Cloudflare assets in .docs-site/lint-my-headers/.")


if __name__ == "__main__":
    main()
