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

asset_hash() {
    "${checksum[@]}" "$1" | cut -d ' ' -f 1
}

mkdir -p -- "$font_dir"
while read -r filename package upstream_path expected; do
    total=$((total + 1))
    target="$font_dir/$filename"
    if [[ -f $target ]] && [[ $(asset_hash "$target") == "$expected" ]]; then
        continue
    fi
    url="https://cdn.jsdelivr.net/npm/$package@$font_version/$upstream_path"
    download_path=$(mktemp "$font_dir/.download.XXXXXX")
    curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
        --connect-timeout 10 --max-time 30 --output "$download_path" "$url"
    if [[ $(asset_hash "$download_path") != "$expected" ]]; then
        printf 'SHA-256 mismatch for %s; documentation build stopped.\n' "$filename" >&2
        exit 1
    fi
    mv -f -- "$download_path" "$target"
    download_path=""
    downloaded=$((downloaded + 1))
done <<'ASSETS'
manrope-latin-wght-normal.woff2 @fontsource-variable/manrope files/manrope-latin-wght-normal.woff2 a30ddcd349703aff7464c34bef3fffdff405ee50c113440d7c8693c02d210972
ibm-plex-sans-latin-wght-normal.woff2 @fontsource-variable/ibm-plex-sans files/ibm-plex-sans-latin-wght-normal.woff2 e2291e842cf5af167122a22881a740c7f2dda7716f1e8cd76680264f4a859470
ibm-plex-mono-latin-400-normal.woff2 @fontsource/ibm-plex-mono files/ibm-plex-mono-latin-400-normal.woff2 08949f728dc52d528e69b1667d15c89a5686a4ee9a296ff90983985f99c380f7
manrope-LICENSE.txt @fontsource-variable/manrope LICENSE d826ab6583b12c26807d8716a545bdbbb672df04f48608a364ba9efdbe501c30
ibm-plex-sans-LICENSE.txt @fontsource-variable/ibm-plex-sans LICENSE d0283623ef57e722fd0eb688a8041589670c608ab780cd3612d06ba6f153d3fd
ibm-plex-mono-LICENSE.txt @fontsource/ibm-plex-mono LICENSE 23b0a9d0c6d3f140a0b77e483c5cfa6bba574325ef5cb189ed9f2fec4884533f
ASSETS

printf 'Prepared %s documentation font assets (%s downloaded).\n' "$total" "$downloaded"
