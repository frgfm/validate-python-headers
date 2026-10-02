#!/usr/bin/env bash
# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

set -euo pipefail
export LC_ALL=C

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
binary="$project_root/target/release/lmh"
if [[ ! -f $binary && -f $binary.exe ]]; then
    binary="$binary.exe"
fi
files=1000
runs=7

usage() {
    printf '%s\n' 'Usage: benchmark_headers.sh [--binary PATH] [--files N] [--runs N]'
    printf '%s\n' 'Time native checks on a temporary fixture spanning all nine languages.'
}

fail() {
    printf '%s\n' "$1" >&2
    exit 2
}

while (( $# )); do
    case "$1" in
        --binary|--files|--runs)
            (( $# >= 2 )) || fail "Missing value for $1"
            case "$1" in
                --binary) binary=$2 ;;
                --files) files=$2 ;;
                --runs) runs=$2 ;;
            esac
            shift 2
            ;;
        -h|--help) usage; exit 0 ;;
        *) fail "Unknown option: $1" ;;
    esac
done

[[ $files =~ ^[0-9]+$ && $runs =~ ^[0-9]+$ ]] || fail '--files and --runs must be integers'
files=$((10#$files))
runs=$((10#$runs))
(( files >= 9 && runs >= 1 )) || fail '--files must be at least 9 and --runs must be positive'
command -v jq >/dev/null 2>&1 || fail 'The benchmark driver requires jq.'
if command -v sha256sum >/dev/null 2>&1; then
    checksum=(sha256sum)
elif command -v shasum >/dev/null 2>&1; then
    checksum=(shasum -a 256)
else
    fail 'The benchmark driver requires sha256sum or shasum.'
fi
[[ -f $binary && -x $binary ]] || fail "Native binary not executable: $binary"
binary=$(cd -- "$(dirname -- "$binary")" && printf '%s/%s\n' "$PWD" "$(basename -- "$binary")")

languages=(python javascript typescript rust go swift bash c cpp)
extensions=(py js ts rs go swift sh c cpp)
markers=('#' '//' '//' '//' '//' '//' '#' '//' '//')
year=$(date +%Y)
fixture_root=$(mktemp -d "${TMPDIR:-/tmp}/lmh-benchmark.XXXXXX")
trap 'rm -rf -- "$fixture_root"' EXIT
mkdir -p -- "$fixture_root/.templates"

write_fixture() {
    local end_year=$1 language_index language marker template function_index index filename
    local -a sizes=()
    source_bytes=0
    cp -- "$project_root/LICENSE" "$fixture_root/LICENSE"
    cat > "$fixture_root/.lmh.toml" <<CONFIG
owner = "Example Organization"
starting-year = $((year - 2))
license = "Apache-2.0"
languages = ["python", "javascript", "typescript", "rust", "go", "swift", "bash", "c", "cpp"]
paths = ["src"]
CONFIG
    for (( language_index=0; language_index<9; language_index++ )); do
        language=${languages[language_index]}
        marker=${markers[language_index]}
        template="$fixture_root/.templates/$language"
        mkdir -p -- "$fixture_root/src/$language"
        {
            printf '%s Copyright (C) %s-%s, Example Organization.\n\n' "$marker" "$((year - 2))" "$end_year"
            printf '%s This program is licensed under the Apache License 2.0.\n' "$marker"
            printf '%s See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.\n\n' "$marker"
            if [[ $language == go ]]; then
                printf 'package main\n\n'
            fi
            for (( function_index=0; function_index<48; function_index++ )); do
                case "$language" in
                    python) printf 'def value_%d():\n    return %d\n\n' "$function_index" "$function_index" ;;
                    javascript) printf 'function value_%d() { return %d; }\n' "$function_index" "$function_index" ;;
                    typescript) printf 'function value_%d(): number { return %d; }\n' "$function_index" "$function_index" ;;
                    rust) printf 'pub fn value_%d() -> i32 { %d }\n' "$function_index" "$function_index" ;;
                    go) printf 'func value_%d() int { return %d }\n' "$function_index" "$function_index" ;;
                    swift) printf 'func value_%d() -> Int { return %d }\n' "$function_index" "$function_index" ;;
                    bash) printf "value_%d() { printf '%%s\\\\n' '%d'; }\n" "$function_index" "$function_index" ;;
                    c) printf 'int value_%d(void) { return %d; }\n' "$function_index" "$function_index" ;;
                    cpp) printf 'int value_%d() { return %d; }\n' "$function_index" "$function_index" ;;
                esac
            done
        } > "$template"
        sizes+=("$(wc -c < "$template")")
    done
    for (( index=0; index<files; index++ )); do
        language_index=$((index % 9))
        language=${languages[language_index]}
        printf -v filename 'file_%05d.%s' "$index" "${extensions[language_index]}"
        cp -- "$fixture_root/.templates/$language" "$fixture_root/src/$language/$filename"
        source_bytes=$((source_bytes + sizes[language_index]))
    done
}

measure() {
    local expected_exit=$1 sample output exit_code seconds
    local -a samples=()
    local TIMEFORMAT='%3R'
    for (( sample=0; sample<=runs; sample++ )); do
        if { time output=$("$binary" check --output-format json 2> "$fixture_root/stderr"); } \
            2> "$fixture_root/timing"; then
            exit_code=0
        else
            exit_code=$?
        fi
        if [[ $exit_code != "$expected_exit" ]] || ! jq -e -s \
            --argjson count "$files" --argjson stale "$expected_exit" '
                length == 1 and (.[0] |
                    .schema_version == 1 and .checked == $count and .changed == [] and .error == null
                    and (.diagnostics | type == "array")
                    and (.diagnostics | length == (if $stale == 1 then $count else 0 end))
                    and all(.diagnostics[]; .code == "LMH004" and .fixable == true))
            ' <<< "$output" >/dev/null; then
            printf 'Unexpected benchmark result (expected exit %s, got %s).\n' "$expected_exit" "$exit_code" >&2
            cat "$fixture_root/stderr" >&2
            exit 1
        fi
        if (( sample > 0 )); then
            read -r seconds < "$fixture_root/timing"
            samples+=("$seconds")
        fi
    done
    printf '%s\n' "${samples[@]}" | jq -s '
        map((. * 1000) | round) |
        {median_ms: (sort | length as $n |
            if $n % 2 == 1 then .[($n / 2 | floor)]
            else (.[($n / 2) - 1] + .[$n / 2]) / 2 end), samples_ms: .}
    '
}

cd -- "$fixture_root"
write_fixture "$year"
clean=$(measure 0)
write_fixture "$((year - 1))"
stale=$(measure 1)
binary_sha256=$("${checksum[@]}" "$binary" | cut -d ' ' -f 1)
language_json=$(printf '%s\n' "${languages[@]}" | jq -R -s 'split("\n")[:-1]')
jq -n --arg platform "$(uname -sr)" --arg architecture "$(uname -m)" \
    --arg binary_sha256 "$binary_sha256" --argjson files "$files" \
    --argjson languages "$language_json" --argjson source_bytes "$source_bytes" \
    --argjson runs "$runs" --argjson clean "$clean" --argjson stale "$stale" '
        {platform: $platform, architecture: $architecture, binary_sha256: $binary_sha256,
         files: $files, languages: $languages, source_bytes: $source_bytes,
         runs: $runs, clean: $clean, stale: $stale}
    '
