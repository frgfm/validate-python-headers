#!/usr/bin/env bash
# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
font_dir="$project_root/docs/assets/fonts"
font_version=5.3.0
downloaded=0
total=0
download_path=""
trap 'if [[ -n $download_path ]]; then rm -f -- "$download_path"; fi' EXIT

if command -v sha256sum >/dev/null 2>&1; then
    checksum=(sha256sum)
elif command -v shasum >/dev/null 2>&1; then
    checksum=(shasum -a 256)
else
    printf '%s\n' 'Documentation fonts require sha256sum or shasum.' >&2
    exit 1
fi

font_hash() {
    "${checksum[@]}" "$1" | cut -d ' ' -f 1
}

mkdir -p -- "$font_dir"
while read -r filename package expected; do
    total=$((total + 1))
    target="$font_dir/$filename"
    if [[ -f $target ]] && [[ $(font_hash "$target") == "$expected" ]]; then
        continue
    fi
    url="https://cdn.jsdelivr.net/npm/$package@$font_version/files/$filename"
    download_path=$(mktemp "$font_dir/.download.XXXXXX")
    curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
        --connect-timeout 10 --max-time 30 --output "$download_path" "$url"
    if [[ $(font_hash "$download_path") != "$expected" ]]; then
        printf 'SHA-256 mismatch for %s; documentation build stopped.\n' "$filename" >&2
        exit 1
    fi
    mv -f -- "$download_path" "$target"
    download_path=""
    downloaded=$((downloaded + 1))
done <<'FONTS'
manrope-latin-wght-normal.woff2 @fontsource-variable/manrope a30ddcd349703aff7464c34bef3fffdff405ee50c113440d7c8693c02d210972
ibm-plex-sans-latin-wght-normal.woff2 @fontsource-variable/ibm-plex-sans e2291e842cf5af167122a22881a740c7f2dda7716f1e8cd76680264f4a859470
ibm-plex-mono-latin-400-normal.woff2 @fontsource/ibm-plex-mono 08949f728dc52d528e69b1667d15c89a5686a4ee9a296ff90983985f99c380f7
FONTS

printf 'Prepared %s documentation fonts (%s downloaded).\n' "$total" "$downloaded"
