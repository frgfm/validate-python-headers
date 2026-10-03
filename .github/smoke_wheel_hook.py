# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

# /// script
# requires-python = ">=3.11"
# dependencies = ["pre-commit==4.6.2", "prek==0.5.4"]
# ///

import argparse
import json
import os
import shlex
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed local commands
import time
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory


def run(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - fixed commands, no shell
        command, cwd=cwd, env=env, capture_output=True, text=True, check=False
    )


def require(result: subprocess.CompletedProcess, expected: int) -> None:
    if result.returncode != expected:
        raise RuntimeError(f"Expected exit {expected}, got {result.returncode}:\n{result.stdout}{result.stderr}")


def fixture(root: Path, mixed: bool, env: dict[str, str]) -> None:
    root.mkdir()
    root.joinpath("src").mkdir()
    root.joinpath("LICENSE").write_text("Apache-2.0\n", encoding="utf-8")
    languages = ["python", "typescript", "rust"] if mixed else ["python"]
    root.joinpath(".lmh.toml").write_text(
        'owner = "Example Owner"\nstarting-year = 2024\nlicense = "Apache-2.0"\n'
        f'languages = {json.dumps(languages)}\npaths = ["src"]\n',
        encoding="utf-8",
    )
    sources = [("clean.py", "#", "value = 1")]
    if mixed:
        sources.extend([("clean.ts", "//", "const value = 1;"), ("clean.rs", "//", "const VALUE: i32 = 1;")])
    for name, marker, body in sources:
        root.joinpath("src", name).write_text(
            f"{marker} Copyright (C) 2024-{datetime.now().year}, Example Owner.\n\n"
            f"{marker} This program is licensed under the Apache License 2.0.\n"
            f"{marker} See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.\n\n"
            f"{body}\n",
            encoding="utf-8",
        )
    require(run(["git", "init", "--quiet"], root, env), 0)
    require(run(["git", "add", "."], root, env), 0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Test the repository wheel hook with fresh caches and no Rust builds")
    parser.add_argument("--engine", choices=("pre-commit", "prek"), required=True)
    parser.add_argument("--dist", type=Path, required=True)
    args = parser.parse_args()
    engine = shutil.which(args.engine)
    if engine is None:
        raise FileNotFoundError(args.engine)
    artifacts = args.dist.resolve()
    source = next(artifacts.glob("*.tar.gz"))
    if not list(artifacts.glob("*.whl")):
        raise FileNotFoundError("Build a native wheel before testing the hook")
    repository = Path(__file__).resolve().parents[1]
    summary = {"engine": args.engine}

    with TemporaryDirectory(prefix="lmh-wheel-hook-") as temporary:
        base = Path(temporary)
        guards = base / "compiler-guards"
        guards.mkdir()
        marker = base / "compiler-was-invoked"
        for compiler in ("cargo", "rustc"):
            guard = guards / (compiler + ".cmd" if os.name == "nt" else compiler)
            text = (
                f'@echo off\n>"{marker}" echo compiler\nexit /b 99\n'
                if os.name == "nt"
                else f"#!/bin/sh\nprintf compiler > {shlex.quote(str(marker))}\nexit 99\n"
            )
            guard.write_text(text, encoding="utf-8")
            guard.chmod(0o755)
        env = {
            **os.environ,
            "PATH": str(guards) + os.pathsep + os.environ["PATH"],
            "UV_OFFLINE": "true",
            "UV_NO_INDEX": "true",
            "UV_FIND_LINKS": str(artifacts),
            "UV_PYTHON_DOWNLOADS": "never",
            "UV_PYTHON_PREFERENCE": "only-system",
            "PRE_COMMIT_HOME": str(base / "pre-commit-cache"),
            "PREK_HOME": str(base / "prek-cache"),
        }

        for name, mixed in (("python", False), ("mixed", True)):
            root = base / name
            env["UV_CACHE_DIR"] = str(base / (name + "-uv-cache"))
            fixture(root, mixed, env)
            command = [engine, "try-repo", str(repository), "lmh-wheel", "--all-files", "--verbose"]
            before = {path: path.read_bytes() for path in root.joinpath("src").iterdir()}
            for phase in ("cold", "warm"):
                started = time.perf_counter()
                require(run(command, root, env), 0)
                summary[f"{name}_{phase}_seconds"] = round(time.perf_counter() - started, 3)
            if mixed:
                stale = root / "src/clean.ts"
                stale.write_bytes(
                    before[stale].replace(str(datetime.now().year).encode(), str(datetime.now().year - 1).encode(), 1)
                )
                before[stale] = stale.read_bytes()
                result = run(command, root, env)
                require(result, 1)
                if "LMH004" not in result.stdout + result.stderr or "clean.ts" not in result.stdout + result.stderr:
                    raise RuntimeError(f"The hook missed the stale TypeScript header: {result.stdout}{result.stderr}")
            if any(path.read_bytes() != original for path, original in before.items()):
                raise RuntimeError("The check hook changed source bytes")

        source_only = base / "source-only"
        source_only.mkdir()
        shutil.copy2(source, source_only / source.name)
        env["UV_FIND_LINKS"] = str(source_only)
        env["UV_CACHE_DIR"] = str(base / "source-only-uv-cache")
        result = run(command, root, env)
        output = result.stdout + result.stderr
        if result.returncode == 0 or "build" not in output.lower() or "disabled" not in output.lower():
            raise RuntimeError(f"Expected source builds to be rejected: {output}")
        if marker.exists():
            raise RuntimeError("The wheel hook tried to invoke a Rust compiler")
        summary["stale_typescript_reported"] = True
        summary["source_bytes_preserved"] = True
        summary["source_build_rejected"] = True
        print(json.dumps(summary))


if __name__ == "__main__":
    main()
