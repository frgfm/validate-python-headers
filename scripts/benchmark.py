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
from pathlib import Path

from matplotlib.figure import Figure

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
ROOT = Path(__file__).resolve().parents[1]


def run_tool(*args: str) -> str:
    executable = shutil.which(args[0])
    if executable is None:
        raise SystemExit(f"Install {args[0]} first; see README.md#benchmarks.")
    return subprocess.check_output([executable, *args[1:]], cwd=ROOT, text=True)  # ruff: ignore[subprocess-without-shell-equals-true]


def source(language: str, size: int, start: int, end: int) -> bytes:
    _, prefix, statement, suffix = LANGUAGES[language]
    marker = "#" if language in {"python", "bash"} else "//"
    header = (
        f"{marker} Copyright (C) {start}-{end}, Benchmark.\n\n"
        f"{marker} This program is licensed under the Apache License 2.0.\n"
        f"{marker} See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.\n\n"
    )
    code = header + prefix + statement * ((size - len(header + prefix + suffix)) // len(statement)) + suffix
    return code.encode().ljust(size, b"\n")


def measure(binary: Path, root: Path, command: str, profiler: str | None) -> tuple[dict, float, float, int]:
    env = {key: value for key, value in os.environ.items() if key != "GITHUB_OUTPUT"}
    env["TZ"] = "UTC"
    with tempfile.NamedTemporaryFile() as memory, tempfile.TemporaryFile() as output:
        argv = [str(binary), command, "--config", ".lmh.toml", "--output-format", "json"]
        if profiler:
            argv = [profiler, "-q", "-f", "%M", "-o", memory.name, *argv]
        started = time.perf_counter()
        process = subprocess.run(argv, cwd=root, env=env, stdout=output, stderr=subprocess.STDOUT)  # ruff: ignore[subprocess-without-shell-equals-true]
        elapsed = time.perf_counter() - started
        output.seek(0)
        result = json.load(output)
        rss = float(memory.read()) / 1024 if profiler else 0
    return result, elapsed * 1000, rss, process.returncode


def chart(rows: list[dict], metric: str, unit: str, count: int, output: Path) -> None:
    selected = [row for row in rows if row["files"] == count]
    title = {"median_ms": "Latency", "files_per_s": "Throughput", "peak_rss_mib": "Peak memory"}[metric]
    languages = list(dict.fromkeys(row["language"] for row in selected))
    figure = Figure(figsize=(10, 6), layout="constrained")
    axes = figure.subplots()
    for index, workload in enumerate(WORKLOADS):
        bars = axes.barh(
            [i + (index - 1) / 4 for i in range(len(languages))],
            [row[metric] for row in selected if row["workload"] == workload],
            height=0.24,
            label={"clean": "Clean check", "findings": "Check with findings", "fix": "Stale-year fix"}[workload],
            color=("#2563eb", "#d97706", "#16a34a")[index],
        )
        axes.bar_label(bars, fmt="%.1f", padding=3, fontsize=7)
    axes.set(
        yticks=range(len(languages)),
        yticklabels=languages,
        xlabel=unit,
        title=f"{title} · {count:,} files x {selected[0]['bytes'] // count:,} bytes",
    )
    axes.invert_yaxis()
    axes.margins(x=0.15)
    axes.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncols=3, frameon=False)
    figure.savefig(output, metadata={"Date": None})
    figure.savefig(output.with_suffix(".png"), dpi=150)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", nargs="+", type=int, default=[1, 100, 1000, 10000], help="files per workload")
    parser.add_argument("--bytes", type=int, default=1024, help="exact bytes per file (minimum 512)")
    parser.add_argument("--runs", type=int, default=5, help="measured repetitions after one warmup (minimum 3)")
    parser.add_argument("--binary", type=Path, help="benchmark an existing native lmh instead of building")
    parser.add_argument("--output", type=Path, default=ROOT / "target/bench", help="artifact directory")
    args = parser.parse_args()
    if sys.platform not in {"linux", "darwin"}:
        parser.error("peak RSS measurement requires Linux or macOS (Windows: use WSL)")
    if min(args.files) < 1 or args.bytes < 512 or args.runs < 3:
        parser.error("use positive file counts, --bytes >= 512 and --runs >= 3")
    profiler = shutil.which("gtime") or (shutil.which("time") if sys.platform == "linux" else None)
    if profiler is None or "GNU" not in run_tool(profiler, "--version"):
        parser.error("install GNU time: apt install time (Linux) or brew install gnu-time (macOS)")
    if args.binary is None:
        run_tool("cargo", "build", "--release", "--locked", "--bin", "lmh", "--target-dir", str(ROOT / "target"))
    binary = (args.binary or ROOT / "target/release/lmh").resolve()
    year = datetime.now(timezone.utc).year
    samples, rows = [], []
    for language in [*LANGUAGES, "mixed"]:
        languages = list(LANGUAGES) if language == "mixed" else [language]
        contents = {
            lang: (source(lang, args.bytes, year - 2, year), source(lang, args.bytes, year - 2, year - 1))
            for lang in languages
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
                files = []
                for index in range(count):
                    lang = languages[index % len(languages)]
                    path = root / "src" / str(index // 100) / f"file{index}.{LANGUAGES[lang][0]}"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    files.append((path, *contents[lang]))
                for workload, command in WORKLOADS.items():
                    case = {"language": language, "workload": workload, "files": count, "bytes": count * args.bytes}
                    batch = []
                    for trial in range(args.runs + 1):
                        for profile in (None, profiler):
                            for path, clean, stale in files:
                                path.write_bytes(clean if workload == "clean" else stale)
                            result, elapsed, rss, status = measure(binary, root, command, profile)
                            if profile is None:
                                latency = elapsed
                            findings = count if workload == "findings" else 0
                            if (
                                status != bool(findings)
                                or result["error"] is not None
                                or result["checked"] != count
                                or len(result["diagnostics"]) != findings
                                or any(d["code"] != "LMH004" or not d["fixable"] for d in result["diagnostics"])
                                or len(result["changed"]) != (count if command == "fix" else 0)
                                or any(
                                    path.read_bytes() != (stale if findings else clean) for path, clean, stale in files
                                )
                            ):
                                raise RuntimeError(f"Invalid result: {language}/{workload}/{count}: {result['error']}")
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
                    sys.stdout.write(f"{language:12} {workload:8} {count:6} files: {median:9.2f} ms\n")
    write_results(args, binary, samples, rows)


def write_results(args: argparse.Namespace, binary: Path, samples: list[dict], rows: list[dict]) -> None:
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in [("measurements", samples), ("results", rows)]:
        with (args.output / f"{name}.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    for name, metric, unit, count in [
        ("latency", "median_ms", "ms; lower is better", min(args.files)),
        ("throughput", "files_per_s", "files/s; higher is better", max(args.files)),
        ("memory", "peak_rss_mib", "MiB; lower is better", max(args.files)),
    ]:
        chart(rows, metric, unit, count, args.output / f"{name}.svg")
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
    report = [
        "# LMH benchmark\n",
        f"UTC: {datetime.now(timezone.utc).isoformat()}",
        f"Harness commit: {run_tool('git', 'rev-parse', 'HEAD').strip()} (dirty: {bool(run_tool('git', 'status', '--porcelain'))})",
        f"Binary: {run_tool(str(binary), '--version').strip()} · SHA-256: {hashlib.sha256(binary.read_bytes()).hexdigest()}",
        f"Compiler: {run_tool('rustc', '--version').strip() if args.binary is None else 'external binary; see its build metadata'}",
        f"Host: {platform.platform()} · CPU: {cpu} · logical CPUs: {os.cpu_count()} · Python: {platform.python_version()} · Fixtures: {tempfile.gettempdir()}\n",
        f"Reproduce: `uv run scripts/benchmark.py {shlex.join(sys.argv[1:])}`\n",
        (
            f"Deterministic synthetic sources, {args.bytes:,} bytes/file; mixed cycles through all nine languages. "
            f"{args.runs} timing/RSS pairs per case after one untimed warmup pair. Warm filesystem cache; no LMH result cache. "
            "Elapsed time includes startup, discovery, parsing, JSON output and (for fix) writes/revalidation. "
            "Generation, fixture restoration and output validation are outside timing. "
            "RSS is measured in separate GNU time invocations on restored fixtures, excluding profiling overhead from latency "
            "and harness/build memory from RSS. Peak RSS is the maximum across repetitions. "
            "Range is slowest minus fastest time. Every run verifies exit status, file count, findings and exact final bytes. "
            "Findings and fix use stale years in every file. These are absolute measurements, not competitor speedups or real-repository results.\n"
        ),
        "[Summary CSV](results.csv) · [Individual runs](measurements.csv)\n",
        *[f"![{name}](./{name}.png)\n" for name in ("latency", "throughput", "memory")],
        "| " + " | ".join(rows[0]) + " |",
        "|" + "---|" * len(rows[0]),
        *[
            "| " + " | ".join(f"{v:.2f}" if isinstance(v, float) else str(v) for v in row.values()) + " |"
            for row in rows
        ],
    ]
    (args.output / "report.md").write_text("\n".join(report) + "\n")
    images = "".join(
        f'<img alt="{name}" src="data:image/png;base64,{base64.b64encode((args.output / f"{name}.png").read_bytes()).decode()}">'
        for name in ("latency", "throughput", "memory")
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
        '<!doctype html><meta charset="utf-8"><title>LMH benchmark</title>'
        "<style>body{font:16px system-ui;max-width:1100px;margin:2em auto;padding:0 1em}"
        "img{width:100%}pre{white-space:pre-wrap}table{border-collapse:collapse}th,td{padding:.4em;border:1px solid #ddd}</style>"
        '<h1>LMH benchmark</h1><p><a href="results.csv">Summary CSV</a> · <a href="measurements.csv">Individual runs</a></p>'
        + images
        + "<details><summary>Methodology and complete results</summary><pre>"
        + html.escape("\n".join(report[1:8]))
        + "</pre>"
        + table
        + "</table></details>\n"
    )
    sys.stdout.write(f"Artifacts: {args.output}\n")


if __name__ == "__main__":
    main()
