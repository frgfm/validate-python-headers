#!/usr/bin/env bash
# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

set -euo pipefail

usage() {
    printf '%s\n' "Usage: bash $0 --engine {pre-commit|prek} --dist DIRECTORY"
}

fail() {
    printf '%s\n' "$*" >&2
    exit 1
}

engine=
artifacts=
while [[ $# -gt 0 ]]; do
    case "$1" in
        --engine|--dist)
            [[ $# -ge 2 ]] || fail "Missing value for $1"
            if [[ $1 == --engine ]]; then engine=$2; else artifacts=$2; fi
            shift 2
            ;;
        --help|-h) usage; exit 0 ;;
        *) usage >&2; fail "Unknown argument: $1" ;;
    esac
done
case "$engine" in
    pre-commit) package=pre-commit==4.6.2 ;;
    prek) package=prek==0.5.4 ;;
    *) usage >&2; fail 'Select pre-commit or prek.' ;;
esac
[[ -d $artifacts ]] || fail 'Provide a distribution directory from make package-check.'
artifacts=$(cd -- "$artifacts" && pwd -P)
project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
shopt -s nullglob
wheels=("$artifacts"/*.whl)
sources=("$artifacts"/*.tar.gz)
[[ ${#wheels[@]} -gt 0 && ${#sources[@]} -eq 1 ]] || fail 'Build a native wheel and one source archive before testing.'

windows=false
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) windows=true ;; esac
native_path() {
    if $windows; then cygpath -w "$1"; else printf '%s\n' "$1"; fi
}

# pre-commit needs the checkout and fixtures on the same Windows drive.
temporary=$(mktemp -d "$project_root/../lmh-wheel-hook.XXXXXX")
trap 'rm -rf -- "$temporary"' EXIT

# Install the test runner before making hook installs offline and wheel-only.
uv venv --no-config --python '>=3.11' "$temporary/tools"
if $windows; then
    tools_python="$temporary/tools/Scripts/python.exe"
    engine_bin="$temporary/tools/Scripts/$engine.exe"
else
    tools_python="$temporary/tools/bin/python"
    engine_bin="$temporary/tools/bin/$engine"
fi
uv pip install --no-config --python "$tools_python" "$package"

guards="$temporary/compiler-guards"
mkdir -p -- "$guards"
export LMH_TEST_COMPILER_MARKER
LMH_TEST_COMPILER_MARKER=$(native_path "$temporary/compiler-was-invoked")
for compiler in cargo rustc; do
    if $windows; then
        cat > "$guards/$compiler.cmd" <<'CMD'
@echo off
>"%LMH_TEST_COMPILER_MARKER%" echo compiler
exit /b 99
CMD
    else
        cat > "$guards/$compiler" <<'SH'
#!/bin/sh
printf compiler > "$LMH_TEST_COMPILER_MARKER"
exit 99
SH
        chmod +x "$guards/$compiler"
    fi
done
export PATH="$guards:$PATH"
export UV_OFFLINE=true UV_NO_INDEX=true UV_PYTHON_DOWNLOADS=never UV_PYTHON_PREFERENCE=only-system
export UV_FIND_LINKS PRE_COMMIT_HOME PREK_HOME UV_CACHE_DIR
UV_FIND_LINKS=$(native_path "$artifacts")
PRE_COMMIT_HOME=$(native_path "$temporary/pre-commit-cache")
PREK_HOME=$(native_path "$temporary/prek-cache")
year=$(date +%Y)

write_source() {
    local path=$1 marker=$2 body=$3 end_year=$4
    printf '%s\n' \
        "$marker Copyright (C) 2024-$end_year, Example Owner." '' \
        "$marker This program is licensed under the Apache License 2.0." \
        "$marker See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details." '' \
        "$body" > "$path"
}

run_hook() (
    cd -- "$fixture"
    "$engine_bin" try-repo "$project_root" lmh-wheel --all-files --verbose
)

expect_hook() {
    local expected=$1 status=0
    TIMEFORMAT='%3R'
    { time run_hook > "$temporary/hook.log" 2>&1; } 2> "$temporary/time.log" || status=$?
    if [[ $status -ne $expected ]]; then
        cat "$temporary/hook.log" >&2
        fail "Expected exit $expected, got $status."
    fi
}

for name in python mixed; do
    fixture="$temporary/$name"
    mkdir -p -- "$fixture/src" "$fixture/expected"
    UV_CACHE_DIR=$(native_path "$temporary/$name-uv-cache")
    languages='["python"]'
    if [[ $name == mixed ]]; then languages='["python", "typescript", "rust"]'; fi
    printf 'Apache-2.0\n' > "$fixture/LICENSE"
    cat > "$fixture/.lmh.toml" <<TOML
owner = "Example Owner"
starting-year = 2024
license = "Apache-2.0"
languages = $languages
paths = ["src"]
TOML
    write_source "$fixture/src/clean.py" '#' 'value = 1' "$year"
    if [[ $name == mixed ]]; then
        write_source "$fixture/src/clean.ts" '//' 'const value = 1;' "$year"
        write_source "$fixture/src/clean.rs" '//' 'const VALUE: i32 = 1;' "$year"
    fi
    cp -- "$fixture"/src/* "$fixture/expected/"
    git -C "$fixture" init --quiet
    git -C "$fixture" add .
    for phase in cold warm; do
        expect_hook 0
        printf '%s %s %s: %s seconds\n' "$engine" "$name" "$phase" "$(cat "$temporary/time.log")"
    done
    if [[ $name == mixed ]]; then
        write_source "$fixture/src/clean.ts" '//' 'const value = 1;' "$((year - 1))"
        cp -- "$fixture/src/clean.ts" "$fixture/expected/clean.ts"
        expect_hook 1
        output=$(cat "$temporary/hook.log")
        [[ $output == *LMH004* && $output == *clean.ts* ]] || fail "The hook missed the stale TypeScript header: $output"
    fi
    for source in "$fixture"/src/*; do
        cmp -s -- "$source" "$fixture/expected/${source##*/}" || fail "The check hook changed source bytes: $source"
    done
done

mkdir -- "$temporary/source-only"
cp -- "${sources[0]}" "$temporary/source-only/"
UV_FIND_LINKS=$(native_path "$temporary/source-only")
UV_CACHE_DIR=$(native_path "$temporary/source-only-uv-cache")
status=0
run_hook > "$temporary/hook.log" 2>&1 || status=$?
output=$(tr '[:upper:]' '[:lower:]' < "$temporary/hook.log")
[[ $status -ne 0 && $output == *build* && $output == *disabled* ]] || fail "Expected source builds to be rejected: $output"
[[ ! -e $temporary/compiler-was-invoked ]] || fail 'The wheel hook tried to invoke a Rust compiler.'
printf '%s\n' "$engine: stale TypeScript reported; source bytes preserved; source builds rejected; no Rust compiler invoked."
