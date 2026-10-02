#!/usr/bin/env bash

# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

set -euo pipefail
export LC_ALL=C TZ=UTC
unset GITHUB_OUTPUT
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
binary='' compare='' baseline='' render=''
output="$root/target/bench" bytes=1024 runs=5
counts=(1 100 1000 10000)
languages=(python javascript typescript rust go swift bash c cpp)
extensions=(py js ts rs go swift sh c cpp)
markers=('#' '//' '//' '//' '//' '//' '#' '//' '//')
prefixes=($'def bench():\n' $'function bench() {\n  let value = 0;\n' $'function bench(): number {\n  let value = 0;\n' $'fn bench() -> i32 {\n    let mut value = 0;\n' $'package bench\nfunc bench() int {\n    value := 0\n' $'func bench() -> Int {\n    var value = 0\n' $'bench() {\n    value=0\n' $'int bench(void) {\n    int value = 0;\n' $'int bench() {\n    int value = 0;\n')
statements=($'    value = 1\n' $'  value += 1;\n' $'  value += 1;\n' $'    value += 1;\n' $'    value += 1\n' $'    value += 1\n' $'    value=$((value + 1))\n' $'    value += 1;\n' $'    value += 1;\n')
suffixes=('' $'}\n' $'  return value;\n}\n' $'    value\n}\n' $'    return value\n}\n' $'    return value\n}\n' $'}\n' $'    return value;\n}\n' $'    return value;\n}\n')
notice=$'This program is licensed under the Apache License 2.0.\nSee LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.'
fail() { printf '%s\n' "$*" >&2; exit 2; }
absolute() { printf '%s/%s\n' "$(cd -- "$(dirname -- "$1")" && pwd)" "$(basename -- "$1")"; }
while (( $# )); do
    case "$1" in
        --files)
            counts=(); shift
            while (( $# )) && [[ $1 != --* ]]; do counts+=("$1"); shift; done
            (( ${#counts[@]} )) || fail 'Missing file counts'
            ;;
        --binary|--compare|--baseline|--output|--bytes|--runs|--render)
            (( $# >= 2 )) || fail "Missing value for $1"
            case "$1" in
                --binary) binary=$2 ;; --compare) compare=$2 ;; --baseline) baseline=$2 ;;
                --output) output=$2 ;; --bytes) bytes=$2 ;; --runs) runs=$2 ;; --render) render=$2 ;;
            esac
            shift 2 ;;
        -h|--help)
            printf '%s\n' 'Usage: benchmark.sh [--files N ...] [--bytes N] [--runs N]' \
                '  [--binary LMH] [--compare HAWKEYE] [--baseline PREVIOUS_LMH] [--output DIR]' \
                '  [--render RESULTS_CSV]  Render an existing snapshot without running tools.' \
                'Requires Bash, jq, gnuplot and GNU time (Linux/macOS; Windows: WSL).'
            exit 0 ;;
        *) fail "Unknown option: $1" ;;
    esac
done
for n in "$bytes" "$runs" "${counts[@]}"; do
    [[ $n =~ ^[0-9]+$ ]] || fail 'Use positive integers'
    (( 10#$n > 0 )) || fail 'Use positive integers'
done
bytes=$((10#$bytes)); runs=$((10#$runs))
(( bytes >= 512 && runs >= 3 )) || fail 'Use --bytes >= 512 and --runs >= 3'
for tool in jq gnuplot; do command -v "$tool" >/dev/null || fail "Install $tool first; see docs/benchmarks.md"; done
mkdir -p -- "$output"; output=$(cd -- "$output" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/lmh-bench.XXXXXX")
trap 'rm -rf -- "$work"' EXIT
if [[ -z $render ]]; then
    profiler=$(type -P gtime || type -P time) || fail 'Install GNU time'
    [[ $("$profiler" --version) == *GNU* ]] || fail 'Install GNU time (brew install gnu-time on macOS)'
    if command -v sha256sum >/dev/null; then checksum=(sha256sum); else checksum=(shasum -a 256); fi
    if [[ -z $binary ]]; then cargo build --release --locked --bin lmh --manifest-path "$root/Cargo.toml" --target-dir "$root/target"; binary="$root/target/release/lmh"; fi
    binary=$(absolute "$binary")
    [[ -z $baseline ]] || baseline=$(absolute "$baseline")
    if [[ -n $compare ]]; then
        compare=$(absolute "$compare")
        [[ $("$compare" --version) == 'hawkeye 7.2.0' ]] || fail '--compare requires HawkEye 7.2.0'
    fi
    year=$(date -u +%Y)
    mkdir -p "$work/templates" "$work/fixture"
    cp "$root/LICENSE" "$work/fixture/LICENSE"
    # Both accepted header formats get exactly the same statements and byte count.
    for (( lang=0; lang<9; lang++ )); do
        marker=${markers[lang]}
        for style in lmh hawkeye; do
            for state in clean stale; do
                end=$year; [[ $state != stale ]] || end=$((year-1))
                printf -v header '%s Copyright (C) %s-%s, Benchmark.\n' "$marker" "$((year-2))" "$end"
                if [[ $style == hawkeye ]]; then header+="$marker"; fi
                header+=$'\n'
                while IFS= read -r line; do header+="$marker $line"$'\n'; done <<< "$notice"
                header+=$'\n'
                budget=$((bytes-${#header}-${#prefixes[lang]}-${#suffixes[lang]}))
                [[ $style == hawkeye ]] || budget=$((budget-${#marker}))
                template="$work/templates/$style-$state-${languages[lang]}"
                {
                    printf '%s%s' "$header" "${prefixes[lang]}"
                    for (( i=0; i<budget/${#statements[lang]}; i++ )); do printf '%s' "${statements[lang]}"; done
                    printf '%s' "${suffixes[lang]}"
                } > "$template"
                padding=$((bytes-$(wc -c < "$template")))
                for (( i=0; i<padding; i++ )); do printf '\n'; done >> "$template"
            done
        done
    done
    printf 'tool,language,workload,files,bytes,run,elapsed_ms,peak_rss_mib\n' > "$output/measurements.csv"
    # Batch restoration and checksum validation avoid one subprocess per file.
    restore() {
        awk -F '\t' -v dir="$work/templates" -v style="$1" -v state="$2" '
            !($2 in text) { f=dir "/" style "-" state "-" $2; while ((getline line < f)>0) text[$2]=text[$2] line "\n"; close(f) }
            { printf "%s",text[$2] > $1; close($1) }
        ' "$work/paths"
    }
    validate() {
        expected_status=0; [[ $workload != findings ]] || expected_status=1
        (( status == expected_status )) || fail "Unexpected exit $status: $tool/$language/$workload"
        jq -e --arg tool "$tool" --arg workload "$workload" --argjson n "$count" '
            if $tool=="hawkeye" then (.files|length)==$n and all(.files[]; .outcome==(if $workload=="clean" then "clean" else "replace" end))
            else .schema_version==1 and .error==null and .checked==$n
                and (.changed|length)==(if $workload=="fix" then $n else 0 end)
                and (.diagnostics|length)==(if $workload=="findings" then $n else 0 end)
                and all(.diagnostics[]; .code=="LMH004" and .fixable==true) end
        ' "$work/result.json" >/dev/null || fail "Invalid result: $tool/$language/$workload"
        expected=clean; [[ $workload != findings ]] || expected=stale
        (cd "$work/fixture"; "${checksum[@]}" --check --quiet "$work/$style-$expected.sha") || fail 'Source bytes differ from expected hashes'
    }
    for language in "${languages[@]}" mixed; do
        selected=("$language"); tools=(lmh); executables=("$binary")
        if [[ $language == mixed ]]; then
            selected=("${languages[@]}")
            if [[ -n $compare ]]; then tools+=(hawkeye); executables+=("$compare"); fi
            if [[ -n $baseline ]]; then tools+=(before); executables+=("$baseline"); fi
        fi
        language_json=$(printf '%s\n' "${selected[@]}" | jq -Rsc 'split("\n")[:-1]')
        printf 'owner="Benchmark"\nstarting-year=%s\nlicense="Apache-2.0"\nlanguages=%s\npaths=["src"]\n' "$((year-2))" "$language_json" > "$work/fixture/.lmh.toml"
        header=$(printf 'Copyright (C) %s-%s, Benchmark.\n\n%s' "$((year-2))" "$year" "$notice" | jq -Rs .)
        printf '[header]\ntext=%s\n[files]\nroot="src"\n[git]\nignore="disable"\nfile_attrs="disable"\n[[rules]]\nextensions=["py","sh"]\nstyle_out="script"\n[[rules]]\nextensions=["js","ts","rs","go","swift","c","cpp"]\nstyle_out="doubleslash"\n' "$header" > "$work/fixture/.licenserc.toml"
        while read -r count; do
            count=$((10#$count))
            [[ $language != mixed ]] || (( count >= 9 )) || continue
            rm -rf -- "$work/fixture/src"; : > "$work/paths"
            for (( i=0; i<count; i+=100 )); do mkdir -p "$work/fixture/src/$((i/100))"; done
            for (( i=0; i<count; i++ )); do
                lang=$((i%9)); [[ $language == mixed ]] || for (( lang=0; lang<9; lang++ )); do [[ ${languages[lang]} != "$language" ]] || break; done
                printf '%s\t%s\n' "$work/fixture/src/$((i/100))/file$i.${extensions[lang]}" "${languages[lang]}" >> "$work/paths"
            done
            for style in lmh hawkeye; do
                for state in clean stale; do
                    for lang in "${selected[@]}"; do printf '%s\t%s\n' "$lang" "$("${checksum[@]}" "$work/templates/$style-$state-$lang" | cut -d ' ' -f 1)"; done > "$work/hashes"
                    awk -F '\t' -v prefix="$work/fixture/" 'NR==FNR {hash[$1]=$2;next} {p=substr($1,length(prefix)+1);print hash[$2] "  " p}' "$work/hashes" "$work/paths" > "$work/$style-$state.sha"
                done
            done
            for workload in clean findings fix; do
                state=stale; [[ $workload != clean ]] || state=clean
                for (( trial=0; trial<=runs; trial++ )); do
                    # Rotation/reversal balances order reproducibly, including the warmup.
                    for (( offset=0; offset<${#tools[@]}; offset++ )); do
                        index=$(((trial+offset*(1-2*(trial%2))+9*${#tools[@]})%${#tools[@]}))
                        tool=${tools[index]}; executable=${executables[index]}; style=lmh; config=.lmh.toml
                        command=check; [[ $workload != fix ]] || command=fix
                        if [[ $tool == hawkeye ]]; then style=hawkeye; config=.licenserc.toml; [[ $workload != fix ]] || command=format; fi
                        restore "$style" "$state"
                        TIMEFORMAT='%3R'
                        if { time (cd "$work/fixture"; "$executable" "$command" --config "$config" --output-format json > "$work/result.json" 2> "$work/stderr"); } 2> "$work/clock"; then status=0; else status=$?; fi
                        validate
                        seconds=$(< "$work/clock"); elapsed=$((10#${seconds%.*}*1000+10#${seconds#*.}))
                        (( elapsed > 0 )) || fail 'Below Bash millisecond resolution; use more files'
                        restore "$style" "$state"
                        if (cd "$work/fixture"; "$profiler" -q -f '%M' -o "$work/rss" "$executable" "$command" --config "$config" --output-format json > "$work/result.json" 2> "$work/stderr"); then status=0; else status=$?; fi
                        validate
                        if (( trial )); then
                            rss=$(awk '{printf "%.6f",$1/1024}' "$work/rss")
                            printf '%s,%s,%s,%s,%s,%s,%s,%s\n' "$tool" "$language" "$workload" "$count" "$((count*bytes))" "$trial" "$elapsed" "$rss" >> "$output/measurements.csv"
                        fi
                    done
                done
                printf '%-12s %-8s %6s files: measured %s tools\n' "$language" "$workload" "$count" "${#tools[@]}"
            done
        done < <(printf '%s\n' "${counts[@]}" | sort -nu)
    done
    jq -Rn '(input|split(",")) as $keys | [inputs|split(",")|to_entries|map({key:$keys[.key],value:.value})|from_entries|.files|=tonumber|.bytes|=tonumber|.elapsed_ms|=tonumber|.peak_rss_mib|=tonumber]
        | group_by([.tool,.language,.workload,.files]) | map(.[0] as $first | (map(.elapsed_ms)|sort) as $times | length as $n
            | (($times[($n/2|floor)]+$times[(($n-1)/2|floor)])/2) as $median
            | {tool:$first.tool,language:$first.language,workload:$first.workload,files:$first.files,bytes:$first.bytes,median_ms:$median,
               range_ms:($times[-1]-$times[0]),files_per_s:($first.files*1000/$median),mib_per_s:($first.bytes*1000/$median/1048576),peak_rss_mib:(map(.peak_rss_mib)|max)})' "$output/measurements.csv" > "$work/results.json"
    jq -r '(.[0]|keys_unsorted) as $keys | ($keys|@csv),(.[]|[.[$keys[]]]|@csv)' "$work/results.json" > "$output/results.csv"
    jq -n --arg utc "$(date -u +%FT%TZ)" --arg commit "$(git -C "$root" rev-parse HEAD)" --arg dirty "$(git -C "$root" status --porcelain)" \
        --arg host "$(uname -smr)" --arg compiler "$(rustc --version)" --arg clock 'Bash builtin time; millisecond precision' \
        --arg storage "$(df -P "${TMPDIR:-/tmp}" | tail -1)" --argjson bytes "$bytes" --argjson runs "$runs" \
        --arg version "$("$binary" --version)" --arg sha "$("${checksum[@]}" "$binary" | cut -d ' ' -f 1)" \
        --arg hawkeye_sha "${compare:+$("${checksum[@]}" "$compare" | cut -d ' ' -f 1)}" --arg before_sha "${baseline:+$("${checksum[@]}" "$baseline" | cut -d ' ' -f 1)}" \
        '{recorded_utc:$utc,harness_commit:$commit,harness_dirty:($dirty!=""),host:$host,compiler:$compiler,clock:$clock,fixture_storage:$storage,
          bytes_per_file:$bytes,runs:$runs,lmh_version:$version,binary_sha256:{lmh:$sha,hawkeye:$hawkeye_sha,before:$before_sha}}' > "$output/environment.json"
else
    jq -Rn '(input|split(",")|map(gsub("\"";""))) as $keys | [inputs|split(",")|map(gsub("\"";""))|to_entries|map({key:$keys[.key],value:.value})|from_entries
        |.files|=tonumber|.bytes|=tonumber|.median_ms|=tonumber|.peak_rss_mib|=tonumber]' "$render" > "$work/results.json"
    [[ $(absolute "$render") == "$output/results.csv" ]] || cp "$render" "$output/results.csv"
    if [[ -f $(dirname -- "$render")/environment.json ]] && [[ $(absolute "$(dirname -- "$render")/environment.json") != "$output/environment.json" ]]; then
        cp "$(dirname -- "$render")/environment.json" "$output/environment.json"
    fi
fi
for chart in check fix; do
    workload=clean; [[ $chart != fix ]] || workload=fix
    jq -r --arg w "$workload" 'map(select(.workload==$w))
        | if any(.language=="mixed") then map(select(.language=="mixed")) else map(select(.tool=="lmh")) end
        | group_by(.files) | map(sort_by({lmh:1,hawkeye:2,before:3}[.tool]))
        | map(map([.files,(if .language=="mixed" then {lmh:"LMH",hawkeye:"HawkEye",before:"LMH before"}[.tool] else .language end),
            .median_ms,{lmh:1,hawkeye:2,before:3}[.tool]] | @tsv) | join("\n")) | join("\n\n\n")' "$work/results.json" > "$work/$chart.dat"
done
jq -r 'map(select(.tool=="lmh")) | (map(.files)|max) as $n | map(select(.files==$n)) | group_by(.language)[]
    | [.[0].language,([.[]|select(.workload=="clean")|.peak_rss_mib][0]),([.[]|select(.workload=="findings")|.peak_rss_mib][0]),([.[]|select(.workload=="fix")|.peak_rss_mib][0])] | @tsv' "$work/results.json" > "$work/memory.dat"
export BENCH_DATA="$work" BENCH_OUTPUT="$output"
BENCH_BYTES=$(jq '.[0].bytes/.[0].files' "$work/results.json")
BENCH_MAX=$(jq 'map(.files)|max' "$work/results.json")
export BENCH_BYTES BENCH_MAX
plot_locale=$(locale -a | awk 'toupper($0) ~ /UTF-?8/ {print;exit}')
LC_ALL='' LC_NUMERIC=C LC_CTYPE="${plot_locale:-C}" gnuplot "$root/scripts/benchmark.gnuplot"
samples=measurements.csv
if [[ -n $render ]]; then
    samples=results.csv
    if [[ -f $(dirname -- "$render")/comparison-samples.csv ]]; then
        samples=comparison-samples.csv
        [[ $(absolute "$(dirname -- "$render")/$samples") == "$output/$samples" ]] || cp "$(dirname -- "$render")/$samples" "$output/$samples"
    fi
fi
{
    printf '# What will header maintenance cost?\n\n'
    for chart in check fix memory; do printf '![%s](%s.png)\n\n' "$chart" "$chart"; done
    printf 'Bash driver; warm synthetic sources; timings include native CLI startup, JSON output and writes.\n\n'
    printf '[Summary CSV](results.csv) · [Recorded CSV](%s) · [Environment](environment.json)\n' "$samples"
} > "$output/report.md"
{
    cat <<'HTML'
<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LMH · Header maintenance cost</title><style>body{font:16px system-ui;color:#172033;background:#f5f6fa;max-width:1100px;margin:3em auto;padding:0 1.5em}h1{font-size:clamp(2em,5vw,3em);letter-spacing:-.04em}p{line-height:1.6}figure{background:white;border:1px solid #e6e9f2;border-radius:18px;margin:1.5em 0;overflow:hidden}svg{display:block;width:100%;height:auto}input{font:inherit;width:5em}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}</style><body><h1>What will header maintenance cost?</h1><p>Native CLI · synthetic sources · warm cache · all nine languages</p><label>Your existing workflow: <input id="baseline" type="number" min="0.001" step="any" value="10"> seconds</label>
HTML
    jq -r 'map(select(.tool=="lmh" and .language=="mixed" and .workload=="clean"))[] | "<p>\(.files) files: \(.median_ms) ms · <span class=impact data-ms=\(.median_ms)></span></p>"' "$work/results.json"
    for chart in check fix memory; do printf '<figure>'; sed -n '/<svg/,$p' "$output/$chart.svg"; printf '</figure>'; done
    printf '<p><a href="results.csv">Summary CSV</a> · <a href="%s">Recorded CSV</a></p><details><summary>Recorded environment</summary><pre>' "$samples"
    [[ ! -f $output/environment.json ]] || jq -Rs '@html' "$output/environment.json" | jq -r .
    printf '</pre></details><script>const baseline=document.querySelector("#baseline");function update(){document.querySelectorAll(".impact").forEach(e=>e.textContent=baseline.value>0?(e.dataset.ms/baseline.value/10).toFixed(2)+"%% longer":"Enter a positive duration")}baseline.addEventListener("input",update);update()</script></body></html>\n'
} > "$output/report.html"
printf 'Artifacts: %s\n' "$output"
