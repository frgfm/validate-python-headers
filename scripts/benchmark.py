# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib==3.10.8"]
# ///

"""Benchmark the native CLI; run with: uv run scripts/benchmark.py."""

import argparse
import base64
import csv
import hashlib
import html
import json
import os
import platform
import shlex
import shutil
import statistics
import subprocess  # ruff: ignore[suspicious-subprocess-import] - native CLI and build tools, no shell
import sys
import tempfile
import time
from datetime import datetime, timezone
from operator import itemgetter
from pathlib import Path

from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, NullLocator

LANGUAGES = {
    "python": ("py", "def bench():\n", "    value = 1\n", ""),
    "javascript": ("js", "function bench() {\n  let value = 0;\n", "  value += 1;\n", "}\n"),
    "typescript": ("ts", "function bench(): number {\n  let value = 0;\n", "  value += 1;\n", "  return value;\n}\n"),
    "rust": ("rs", "fn bench() -> i32 {\n    let mut value = 0;\n", "    value += 1;\n", "    value\n}\n"),
    "go": ("go", "package bench\nfunc bench() int {\n    value := 0\n", "    value += 1\n", "    return value\n}\n"),
    "swift": ("swift", "func bench() -> Int {\n    var value = 0\n", "    value += 1\n", "    return value\n}\n"),
    "bash": ("sh", "bench() {\n    value=0\n", "    value=$((value + 1))\n", "}\n"),
    "c": ("c", "int bench(void) {\n    int value = 0;\n", "    value += 1;\n", "    return value;\n}\n"),
    "cpp": ("cpp", "int bench() {\n    int value = 0;\n", "    value += 1;\n", "    return value;\n}\n"),
}
WORKLOADS = {"clean": "check", "findings": "check", "fix": "fix"}
CHARTS = ("check", "fix", "memory")
NOTICE = "This program is licensed under the Apache License 2.0.\nSee LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details."
ROOT = Path(__file__).resolve().parents[1]


def run_tool(*args: str) -> str:
    executable = shutil.which(args[0])
    if executable is None:
        raise SystemExit(f"Install {args[0]} first; see README.md#benchmarks.")
    return subprocess.check_output([executable, *args[1:]], cwd=ROOT, text=True)  # ruff: ignore[subprocess-without-shell-equals-true]


def source(language: str, size: int, start: int, end: int, canonical: bool = False) -> bytes:
    _, prefix, statement, suffix = LANGUAGES[language]
    marker = "#" if language in {"python", "bash"} else "//"
    header = f"{marker} Copyright (C) {start}-{end}, Benchmark.\n{marker if canonical else ''}\n"
    header += "".join(f"{marker} {line}\n" for line in NOTICE.splitlines()) + "\n"
    code = header + prefix + statement * ((size - len(header + prefix + suffix)) // len(statement)) + suffix
    return code.encode().ljust(size, b"\n")


def measure(binary: Path, root: Path, command: str, profiler: str | None, tool: str) -> tuple[dict, float, float, int]:
    env = {key: value for key, value in os.environ.items() if key != "GITHUB_OUTPUT"}
    env["TZ"] = "UTC"
    with tempfile.NamedTemporaryFile() as memory, tempfile.TemporaryFile() as output:
        config = ".licenserc.toml" if tool == "hawkeye" else ".lmh.toml"
        argv = [str(binary), command, "--config", config, "--output-format", "json"]
        if profiler:
            argv = [profiler, "-q", "-f", "%M", "-o", memory.name, *argv]
        started = time.perf_counter()
        process = subprocess.run(argv, cwd=root, env=env, stdout=output, stderr=subprocess.STDOUT)  # ruff: ignore[subprocess-without-shell-equals-true]
        elapsed = time.perf_counter() - started
        output.seek(0)
        result = json.load(output)
        rss = float(memory.read()) / 1024 if profiler else 0
    return result, elapsed * 1000, rss, process.returncode


def duration(milliseconds: float) -> str:
    return f"{milliseconds:.1f} ms" if milliseconds < 1000 else f"{milliseconds / 1000:.2f} s"


def chart(rows: list[dict], name: str, output: Path) -> None:
    title = {
        "check": "How much time does a check add?",
        "fix": "How long does a full year update take?",
        "memory": "How much memory will it need?",
    }[name]
    figure = Figure(figsize=(11, 6.2), facecolor="white")
    axes = figure.add_axes((0.10, 0.18, 0.85, 0.58))
    figure.text(0.08, 0.91, title, fontsize=24, weight="bold", color="#172033")
    figure.text(
        0.08,
        0.85,
        f"Native CLI · JSON output · {rows[0]['bytes'] // rows[0]['files']:,} bytes/file · synthetic · warm cache",
        fontsize=11,
        color="#657086",
    )
    axes.spines[["top", "right", "left", "bottom"]].set_visible(False)
    axes.tick_params(axis="both", length=0, labelsize=11, colors="#657086", pad=10)
    axes.set_axisbelow(True)
    axes.grid(axis="x" if name == "memory" else "y", color="#edf0f5")
    native = [row for row in rows if row["tool"] == "lmh"]
    if name == "memory":
        count = max(row["files"] for row in native)
        selected = [row for row in native if row["files"] == count and row["workload"] == "clean"]
        languages = [row["language"] for row in selected]
        for workload, color, offset, label in [
            ("clean", "#6554df", -0.18, "Routine check"),
            ("findings", "#7c899d", 0, "Check with findings"),
            ("fix", "#078b79", 0.18, "Repair"),
        ]:
            values = [row["peak_rss_mib"] for row in native if row["files"] == count and row["workload"] == workload]
            axes.scatter(values, [i + offset for i in range(len(languages))], s=65, color=color, label=label, zorder=3)
        labels = {"javascript": "JavaScript", "typescript": "TypeScript", "cpp": "C++", "c": "C"}
        axes.set(
            yticks=range(len(languages)),
            yticklabels=[labels.get(lang, lang.title()) for lang in languages],
            xlabel="Peak native-process RSS (MiB)",
            xlim=(0, None),
        )
        axes.invert_yaxis()
        caption = f"LMH · {count:,} files · peak across repetitions · harness/build memory excluded"
    else:
        workload = "clean" if name == "check" else "fix"
        selected = [row for row in native if row["workload"] == workload and row["language"] != "mixed"]
        counts = sorted({row["files"] for row in selected})
        lows = [min(row["median_ms"] for row in selected if row["files"] == count) / 1000 for count in counts]
        highs = [max(row["median_ms"] for row in selected if row["files"] == count) / 1000 for count in counts]
        axes.fill_between(counts, lows, highs, color="#e6e9f2", label="LMH · range across nine languages")
        axes.vlines(counts, lows, highs, color="#c2c8da", linewidth=5, alpha=0.5)
        for tool, color, label in [("lmh", "#6554df", "LMH · mixed"), ("hawkeye", "#078b79", "HawkEye · mixed")]:
            series = sorted(
                [
                    row
                    for row in rows
                    if row["tool"] == tool and row["language"] == "mixed" and row["workload"] == workload
                ],
                key=itemgetter("files"),
            )
            if series:
                axes.plot(
                    [row["files"] for row in series],
                    [row["median_ms"] / 1000 for row in series],
                    color=color,
                    linewidth=2.8,
                    marker="o",
                    markersize=7,
                    label=label,
                )
                last = series[-1]
                axes.annotate(
                    duration(last["median_ms"]),
                    (last["files"], last["median_ms"] / 1000),
                    xytext=(-8, 12),
                    textcoords="offset points",
                    ha="right",
                    color=color,
                    weight="bold",
                    fontsize=12,
                )
        axes.set(
            xscale="log",
            xticks=counts,
            xticklabels=[f"{count:,}" for count in counts],
            xlabel="Files selected for this invocation",
            ylabel="Elapsed wall-clock time",
            ylim=(0, None),
        )
        axes.xaxis.set_minor_locator(NullLocator())
        axes.margins(x=0.08, y=0.2)
        scale = 1 if axes.get_ylim()[1] >= 1 else 1000
        axes.yaxis.set_major_formatter(
            FuncFormatter(lambda value, _: f"{value * scale:g} {'s' if scale == 1 else 'ms'}")
        )
        caption = "Measured medians · straight lines connect measured sizes; no extrapolation"
    axes.legend(loc="lower left", bbox_to_anchor=(0, 1.03), ncols=3, frameon=False, fontsize=10, borderaxespad=0)
    figure.text(0.08, 0.035, caption, fontsize=10, color="#657086")
    figure.savefig(output, metadata={"Date": None})
    figure.savefig(output.with_suffix(".png"), dpi=150)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", nargs="+", type=int, default=[1, 100, 1000, 10000], help="files per workload")
    parser.add_argument("--bytes", type=int, default=1024, help="exact bytes per file (minimum 512)")
    parser.add_argument("--runs", type=int, default=5, help="measured repetitions after one warmup (minimum 3)")
    parser.add_argument("--binary", type=Path, help="benchmark an existing native lmh instead of building")
    parser.add_argument("--compare", type=Path, help="also benchmark a HawkEye 7.2.0 binary on mixed-language trees")
    parser.add_argument("--output", type=Path, default=ROOT / "target/bench", help="artifact directory")
    args = parser.parse_args()
    if sys.platform not in {"linux", "darwin"}:
        parser.error("peak RSS measurement requires Linux or macOS (Windows: use WSL)")
    if min(args.files) < 1 or args.bytes < 512 or args.runs < 3:
        parser.error("use positive file counts, --bytes >= 512 and --runs >= 3")
    profiler = shutil.which("gtime") or (shutil.which("time") if sys.platform == "linux" else None)
    if profiler is None or "GNU" not in run_tool(profiler, "--version"):
        parser.error("install GNU time: apt install time (Linux) or brew install gnu-time (macOS)")
    if args.compare and run_tool(str(args.compare.resolve()), "--version").strip() != "hawkeye 7.2.0":
        parser.error("--compare requires HawkEye 7.2.0: cargo install hawkeye --version 7.2.0 --locked")
    if args.binary is None:
        run_tool("cargo", "build", "--release", "--locked", "--bin", "lmh", "--target-dir", str(ROOT / "target"))
    binary = (args.binary or ROOT / "target/release/lmh").resolve()
    year = datetime.now(timezone.utc).year
    samples, rows = [], []
    for language in [*LANGUAGES, "mixed"]:
        languages = list(LANGUAGES) if language == "mixed" else [language]
        tools = {"lmh": binary}
        if language == "mixed" and args.compare:
            tools["hawkeye"] = args.compare.resolve()
        contents = {
            tool: {
                lang: (
                    source(lang, args.bytes, year - 2, year, tool == "hawkeye"),
                    source(lang, args.bytes, year - 2, year - 1, tool == "hawkeye"),
                )
                for lang in languages
            }
            for tool in tools
        }
        for count in sorted(set(args.files)):
            if language == "mixed" and count < len(LANGUAGES):
                continue
            with tempfile.TemporaryDirectory(prefix="lmh-bench-") as directory:
                root = Path(directory)
                root.joinpath("LICENSE").write_bytes(ROOT.joinpath("LICENSE").read_bytes())
                root.joinpath(".lmh.toml").write_text(
                    f'owner = "Benchmark"\nstarting-year = {year - 2}\nlicense = "Apache-2.0"\n'
                    f'languages = {json.dumps(languages)}\npaths = ["src"]\n',
                )
                if "hawkeye" in tools:
                    header = f"Copyright (C) {year - 2}-{year}, Benchmark.\n\n{NOTICE}"
                    config = f'[header]\ntext = {json.dumps(header)}\n[files]\nroot = "src"\n[git]\nignore = "disable"\nfile_attrs = "disable"\n'
                    for extensions, style in [
                        (["py", "sh"], "script"),
                        (["js", "ts", "rs", "go", "swift", "c", "cpp"], "doubleslash"),
                    ]:
                        config += f'[[rules]]\nextensions = {json.dumps(extensions)}\nstyle_out = "{style}"\n'
                    root.joinpath(".licenserc.toml").write_text(config)
                files = []
                for index in range(count):
                    lang = languages[index % len(languages)]
                    path = root / "src" / str(index // 100) / f"file{index}.{LANGUAGES[lang][0]}"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    files.append((path, lang))
                for workload, command in WORKLOADS.items():
                    for tool, executable in tools.items():
                        case = {
                            "tool": tool,
                            "language": language,
                            "workload": workload,
                            "files": count,
                            "bytes": count * args.bytes,
                        }
                        expected = [(path, *contents[tool][lang]) for path, lang in files]
                        batch = []
                        for trial in range(args.runs + 1):
                            for profile in (None, profiler):
                                for path, clean, stale in expected:
                                    path.write_bytes(clean if workload == "clean" else stale)
                                invocation = "format" if tool == "hawkeye" and command == "fix" else command
                                result, elapsed, rss, status = measure(executable, root, invocation, profile, tool)
                                if profile is None:
                                    latency = elapsed
                                findings = count if workload == "findings" else 0
                                if tool == "hawkeye":
                                    valid = len(result["files"]) == count and all(
                                        file["outcome"] == ("clean" if workload == "clean" else "replace")
                                        for file in result["files"]
                                    )
                                else:
                                    valid = (
                                        result["error"] is None
                                        and result["checked"] == count
                                        and len(result["diagnostics"]) == findings
                                        and all(d["code"] == "LMH004" and d["fixable"] for d in result["diagnostics"])
                                        and len(result["changed"]) == (count if command == "fix" else 0)
                                    )
                                if (
                                    status != bool(findings)
                                    or not valid
                                    or any(
                                        path.read_bytes() != (stale if findings else clean)
                                        for path, clean, stale in expected
                                    )
                                ):
                                    raise RuntimeError(
                                        f"Invalid result: {tool}/{language}/{workload}/{count}: {result}"
                                    )
                            if trial:
                                batch.append(latency)
                                samples.append({**case, "run": trial, "elapsed_ms": latency, "peak_rss_mib": rss})
                        median = statistics.median(batch)
                        rows.append({
                            **case,
                            "median_ms": median,
                            "range_ms": max(batch) - min(batch),
                            "files_per_s": count * 1000 / median,
                            "mib_per_s": count * args.bytes * 1000 / median / 1024**2,
                            "peak_rss_mib": max(sample["peak_rss_mib"] for sample in samples[-args.runs :]),
                        })
                        sys.stdout.write(f"{tool:8} {language:12} {workload:8} {count:6} files: {median:9.2f} ms\n")
    write_results(args, binary, samples, rows)


def write_results(args: argparse.Namespace, binary: Path, samples: list[dict], rows: list[dict]) -> None:
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in [("measurements", samples), ("results", rows)]:
        with (args.output / f"{name}.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    for name in CHARTS:
        chart(rows, name, args.output / f"{name}.svg")
    cpu = platform.processor()
    if Path("/proc/cpuinfo").exists():
        cpu = next(
            (
                line.split(":", 1)[1].strip()
                for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")
            ),
            cpu or platform.machine(),
        )
    metadata = [
        f"UTC: {datetime.now(timezone.utc).isoformat()}",
        f"Harness commit: {run_tool('git', 'rev-parse', 'HEAD').strip()} (dirty: {bool(run_tool('git', 'status', '--porcelain'))})",
        f"Binary: {run_tool(str(binary), '--version').strip()} · SHA-256: {hashlib.sha256(binary.read_bytes()).hexdigest()}",
        f"Compiler: {run_tool('rustc', '--version').strip() if args.binary is None else 'external binary; see its build metadata'}",
        f"Host: {platform.platform()} · CPU: {cpu} · logical CPUs: {os.cpu_count()} · Python: {platform.python_version()} · Fixtures: {tempfile.gettempdir()}\n",
        f"Reproduce: `uv run scripts/benchmark.py {shlex.join(sys.argv[1:])}`\n",
    ]
    comparison = (
        "Optional comparison: cargo install hawkeye --version 7.2.0 --locked, then pass --compare /path/to/hawkeye."
    )
    if args.compare:
        competitor = args.compare.resolve()
        metadata.append(
            f"Competitor: {run_tool(str(competitor), '--version').strip()} · SHA-256: {hashlib.sha256(competitor.read_bytes()).hexdigest()}"
        )
        comparison = "HawkEye 7.2.0 compares check/check and fix/format on mixed trees. Both use JSON output, equal file counts/sizes, owner, license and years. Each gets its accepted canonical comment format; HawkEye uses a fixed header template and disabled Git attributes. Validation and safety policies differ, so this measures these tasks rather than equivalent tool features."
    methodology = (
        f"Deterministic synthetic sources, {args.bytes:,} bytes/file; mixed cycles through all nine languages. "
        f"{args.runs} timing/RSS pairs per case after one untimed warmup pair. Warm filesystem cache; no LMH result cache. "
        "Elapsed time includes launching/waiting for the native CLI, discovery, parsing, JSON output and (for fix) writes/revalidation. "
        "Generation, fixture restoration and output validation are outside timing. "
        "RSS uses separate GNU time invocations on restored fixtures, excluding profiling overhead from latency and harness/build memory from RSS. "
        "Peak RSS is the maximum across repetitions. Range is slowest minus fastest time. Every run verifies exit status, file count, findings and exact final bytes. "
        "Findings and fix use stale years in every file. No real-repository or competitor-wide speedup claims. "
        + comparison
    )
    scope = "Times measure the CLI in JSON mode. A serial check adds this wait to your workflow; installation, hook orchestration and CI queueing are excluded. Repairs update stale years in every selected source file; missing or conflicting headers still need review. Results depend on your hardware and source sizes."
    native = [row for row in rows if row["tool"] == "lmh"]
    summary, cards = [], []
    for count in sorted({row["files"] for row in native}):
        selected = [row for row in native if row["files"] == count]
        if any(row["language"] == "mixed" for row in selected):
            selected = [row for row in selected if row["language"] == "mixed"]
        values, bounds = [], []
        for workload in ("clean", "fix"):
            times = [row["median_ms"] for row in selected if row["workload"] == workload]
            low, high = min(times), max(times)
            bounds.append((low, high))
            if low == high:
                values.append(duration(low))
            elif high < 1000:
                values.append(f"{low:.1f} to {duration(high)}")
            else:
                values.append(f"{duration(low)} to {duration(high)}")
        label = "Mixed languages" if selected[0]["language"] == "mixed" else "Range across nine languages"
        summary.append(f"| {count:,} | {values[0]} | {values[1]} | {label} |")
        cards.append(
            f'<article><small>{count:,} selected {"file" if count == 1 else "files"}</small><h2>+{values[0]}</h2><p>per routine check</p><small class="impact" data-low="{bounds[0][0]}" data-high="{bounds[0][1]}"></small><hr><b>{values[1]}</b> to repair all stale years<p class="muted">{label}</p></article>'
        )
    report = [
        "# What will header maintenance cost?\n",
        scope + "\n",
        "| Selected files | Added wait per routine check | Repair all stale years | Scope |",
        "|---|---|---|---|",
        *summary,
        "\nWorkflow slowdown (%) = check time / your existing workflow time * 100. The HTML report lets you enter that baseline.\n",
        "[Summary CSV](results.csv) · [Individual runs](measurements.csv)\n",
        *[f"![{name}](./{name}.png)\n" for name in CHARTS],
        "## Methodology and complete results\n",
        *metadata,
        methodology + "\n",
        "Related tools: [HawkEye](https://github.com/fast/hawkeye/tree/v7.2.0). [addlicense](https://github.com/google/addlicense) leaves existing headers unchanged; [REUSE](https://github.com/fsfe/reuse-tool) checks SPDX compliance. They solve different tasks from stale-year repair.\n",
        "| " + " | ".join(rows[0]) + " |",
        "|" + "---|" * len(rows[0]),
        *[
            "| " + " | ".join(f"{v:.2f}" if isinstance(v, float) else str(v) for v in row.values()) + " |"
            for row in rows
        ],
    ]
    (args.output / "report.md").write_text("\n".join(report) + "\n")
    images = "".join(
        f'<figure><img alt="{name}" src="data:image/png;base64,{base64.b64encode((args.output / f"{name}.png").read_bytes()).decode()}"></figure>'
        for name in CHARTS
    )
    table = "<table><tr>" + "".join(f"<th>{html.escape(key)}</th>" for key in rows[0]) + "</tr>"
    for row in rows:
        table += (
            "<tr>"
            + "".join(
                f"<td>{html.escape(f'{value:.2f}' if isinstance(value, float) else str(value))}</td>"
                for value in row.values()
            )
            + "</tr>"
        )
    (args.output / "report.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LMH · Cost of header maintenance</title>'
        "<style>body{font:16px system-ui;color:#172033;background:#f5f6fa;max-width:1100px;margin:4em auto;padding:0 1.5em}"
        "h1{font-size:clamp(2em,5vw,3.2em);letter-spacing:-.04em;line-height:1.1;max-width:18ch}h2{font-size:1.8em;letter-spacing:-.04em;margin:.5em 0}"
        "p{line-height:1.6}small,.muted{color:#657086}a,.impact{color:#6554df}a{text-underline-offset:4px}"
        ".cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1em;margin:2em 0}"
        "article,figure,details{background:white;border:1px solid #e6e9f2;border-radius:18px}article,details{padding:1.5em}article p{margin:.4em 0}"
        "hr{border:0;border-top:1px solid #edf0f5;margin:1.5em 0}figure{margin:1.5em 0;overflow:hidden}img{display:block;width:100%}"
        "input{font:inherit;width:5em;border:1px solid #c2c8da;border-radius:8px;padding:.4em}summary{cursor:pointer;font-weight:600}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px ui-monospace,monospace;line-height:1.6}.table{overflow:auto}table{border-collapse:collapse;font-size:13px}th,td{padding:.6em;text-align:left;border-bottom:1px solid #edf0f5}</style>"
        "<body><small>LMH / PERFORMANCE</small><h1>What will header maintenance cost?</h1><p>Keep copyright years current. See the wait before adding it to your workflow.</p>"
        '<label>Your workflow duration (editable example): <input id="baseline" type="number" min="0.001" step="any" value="10"> seconds before adding a check.</label>'
        '<section class="cards">' + "".join(cards) + '</section><p class="muted">' + html.escape(scope) + "</p>"
        '<p><a href="results.csv">Summary CSV</a> · <a href="measurements.csv">Individual runs</a> · <a href="https://github.com/fast/hawkeye/tree/v7.2.0">HawkEye 7.2.0</a></p>'
        + images
        + "<details><summary>Methodology and complete results</summary><pre>"
        + html.escape("\n".join([*metadata, methodology]))
        + '</pre><div class="table">'
        + table
        + "</table></div></details>"
        '<script>const baseline=document.querySelector("#baseline");function update(){const seconds=Number(baseline.value);'
        'document.querySelectorAll(".impact").forEach(el=>{const pct=ms=>new Intl.NumberFormat(undefined,{maximumSignificantDigits:2}).format(Number(ms)/seconds/10);'
        'el.textContent=seconds>0&&Number.isFinite(seconds)?(el.dataset.low===el.dataset.high?pct(el.dataset.low):pct(el.dataset.low)+" to "+pct(el.dataset.high))+"% longer than your baseline":"Enter a positive workflow duration";});}'
        'baseline.addEventListener("input",update);update();</script></body></html>\n'
    )
    sys.stdout.write(f"Artifacts: {args.output}\n")


if __name__ == "__main__":
    main()
