#!/usr/bin/env bash
# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
docs_source="$project_root/site"
docs_target="$project_root/.docs-site"

if [[ -L $docs_source || -L $docs_target ]]; then
    printf '%s\n' 'Documentation build directories must not be symlinks.' >&2
    exit 1
fi
if [[ ! -f $docs_source/index.html ]]; then
    printf '%s\n' 'Build documentation with make docs before preparing Cloudflare assets.' >&2
    exit 1
fi

rm -rf -- "$docs_target"
mkdir -p -- "$docs_target"
cp -Rp -- "$docs_source" "$docs_target/lint-my-headers"
printf '%s\n' 'Prepared Cloudflare assets in .docs-site/lint-my-headers/.'
