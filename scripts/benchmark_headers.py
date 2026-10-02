# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

import argparse
import hashlib
import json
import platform
import shutil
import statistics
import subprocess  # ruff: ignore[suspicious-subprocess-import] - explicitly selected local CLI
import sys
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = {
    "python": ("py", "#", "def value_{i}():\n    return {i}\n\n"),
    "javascript": ("js", "//", "function value_{i}() {{ return {i}; }}\n"),
    "typescript": ("ts", "//", "function value_{i}(): number {{ return {i}; }}\n"),
    "rust": ("rs", "//", "pub fn value_{i}() -> i32 {{ {i} }}\n"),
    "go": ("go", "//", "func value_{i}() int {{ return {i} }}\n"),
    "swift": ("swift", "//", "func value_{i}() -> Int {{ return {i} }}\n"),
    "bash": ("sh", "#", "value_{i}() {{ printf '%s\\n' '{i}'; }}\n"),
    "c": ("c", "//", "int value_{i}(void) {{ return {i}; }}\n"),
    "cpp": ("cpp", "//", "int value_{i}() {{ return {i}; }}\n"),
}


def write_fixture(root: Path, count: int, year: int, end_year: int) -> int:
    shutil.copyfile(ROOT / "LICENSE", root / "LICENSE")
    (root / ".lmh.toml").write_text(
        f'owner = "Example Organization"\nstarting-year = {year - 2}\nlicense = "Apache-2.0"\n'
        f'languages = {json.dumps(list(LANGUAGES))}\npaths = ["src"]\n',
        encoding="utf-8",
    )
    total = 0
    for index in range(count):
        language = list(LANGUAGES)[index % len(LANGUAGES)]
        extension, marker, template = LANGUAGES[language]
        notice = (
            f"{marker} Copyright (C) {year - 2}-{end_year}, Example Organization.\n\n"
            f"{marker} This program is licensed under the Apache License 2.0.\n"
            f"{marker} See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.\n\n"
        )
        body = "package main\n\n" if language == "go" else ""
        body += "".join(template.format(i=i) for i in range(48))
        target = root / "src" / language / f"file_{index:05d}.{extension}"
        target.parent.mkdir(parents=True, exist_ok=True)
        data = (notice + body).encode("utf-8")
        target.write_bytes(data)
        total += len(data)
    return total


def measure(binary: Path, root: Path, count: int, runs: int, stale: bool) -> dict[str, object]:
    samples = []
    for sample in range(runs + 1):
        start = perf_counter()
        result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - validated binary, literal arguments
            [str(binary), "check", "--output-format", "json"], cwd=root, capture_output=True, check=False
        )
        elapsed = (perf_counter() - start) * 1000
        output = json.loads(result.stdout)
        diagnostics = output["diagnostics"]
        if (
            result.returncode != int(stale)
            or output["checked"] != count
            or output["changed"]
            or output["error"] is not None
            or len(diagnostics) != (count if stale else 0)
            or any(item["code"] != "LMH004" or not item["fixable"] for item in diagnostics)
        ):
            raise RuntimeError(f"Unexpected benchmark result: {result.stderr.decode()} {output}")
        if sample:
            samples.append(round(elapsed, 3))
    return {"median_ms": round(statistics.median(samples), 3), "samples_ms": samples}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Time native checks on a temporary fixture spanning all nine languages."
    )
    executable = "lmh.exe" if sys.platform == "win32" else "lmh"
    parser.add_argument("--binary", type=Path, default=ROOT / "target/release" / executable)
    parser.add_argument("--files", type=int, default=1000)
    parser.add_argument("--runs", type=int, default=7)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    if args.files < len(LANGUAGES) or args.runs < 1:
        parser.error("--files must be at least 9 and --runs must be positive")
    year = datetime.now().year
    with TemporaryDirectory(prefix="lmh-benchmark-") as temporary:
        root = Path(temporary)
        byte_count = write_fixture(root, args.files, year, year)
        clean = measure(binary, root, args.files, args.runs, stale=False)
        write_fixture(root, args.files, year, year - 1)
        stale = measure(binary, root, args.files, args.runs, stale=True)
    report = {
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "files": args.files,
        "languages": list(LANGUAGES),
        "source_bytes": byte_count,
        "runs": args.runs,
        "clean": clean,
        "stale": stale,
    }
    sys.stdout.write(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
