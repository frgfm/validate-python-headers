# Lint My Headers

A Rust CLI that checks Python copyright/license headers and safely refreshes recognized stale years. It never chooses ownership or licensing, inserts missing headers, or claims legal/SPDX/REUSE compliance.

## Quick start

Install a published release, or build this checkout with Rust 1.93:

```shell
uv tool install lint-my-headers
# From source:
cargo build --release --locked
```

PyPI wheels contain native `lmh` and `lint-my-headers` executables; source distributions require Rust. Python 3.11+ is needed only for PyPI tooling and the optional launchers. `python -m lint_my_headers` replaces Python with the native process on Unix; Windows starts a child process. The callable `main(argv)` always returns the child's exit code. Checking and fixing run entirely in Rust.

Declare the policy in `pyproject.toml`:

```toml
[tool.lint-my-headers]
owner = "Example Organization"
starting-year = 2024
license = "Apache-2.0"
paths = ["src", "tests"]
ignore-files = ["version.py"]
ignore-folders = ["src/generated"]
```

```shell
lmh check                              # Read-only; configured paths
lmh check src/package tests/test_api.py # Explicit paths
lmh fix                                # Safe stale-year repairs only
lmh --version
lmh check --help
```

A valid header in 2026:

```python
# Copyright (C) 2024-2026, Example Organization.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.
```

Diagnostics name the location, reason, and repair eligibility:

```text
src/example.py:1:1: LMH004 copyright year ends at 2025; expected 2026 [fixable]
```

Exit codes: **0** clean, **1** unresolved findings, **2** invocation/configuration/I/O error. `fix` preserves the creation year and changes no other bytes. Unknown, missing, malformed, duplicate, wrong-owner, or future-dated headers require manual review.

## Configuration and safety

CLI policy options override configuration; `--config` selects another `pyproject.toml`. Configured paths are relative to that file; explicit CLI paths are relative to the invocation directory.

| Key / CLI option | Meaning and default |
| --- | --- |
| `owner` / `--owner` | Required exact single-line copyright owner. |
| `starting-year` / `--starting-year` | Required earliest accepted file creation year. |
| `license` / `--license` | SPDX identifier selecting a prose notice; requires local `LICENSE`. |
| `license-notice` / `--license-notice` | Custom notice file; configure exactly one license source. |
| `paths` / positional paths | Selected files or directories; default `.`. |
| `ignore-files` / `--ignore-files` | Exact basenames; default `__init__.py`. |
| `ignore-folders` / `--ignore-folders` | Excluded subtrees; default `.github`. |

CLI ignore lists are comma-separated; configuration lists are TOML arrays. Exclusions also apply to explicit inputs. Diagnostics use sorted, project-relative `/` paths, including `..` for explicitly selected external files.

Python shebangs, UTF-8 BOMs, and PEP 263 cookies are preserved. Verified encodings are UTF-8, ASCII, Latin-1, and Windows-1252; other codecs fail without repair. Ambiguous newer Python string syntax also fails closed.

Directory discovery skips symlinks/reparse points. Explicit linked files may be checked, but repairs refuse symlinks, linked parents, reparse points, and multiple hard links. Before atomic replacement, file identity and contents are revalidated; the repaired bytes must pass the same parser.

The bundled SPDX snapshot is v3.28.0. All previously accepted v3.17 names/URLs remain valid, including the legacy `KiCad-libraries-exception`. Compound SPDX expressions and new exception semantics are unsupported.

## Agents and JSON

Use `lmh check --output-format json`. Successfully parsed JSON-mode commands write only JSON to stdout; malformed CLI syntax remains a stderr usage error.

```json
{
  "schema_version": 1,
  "tool_version": "0.6.0",
  "command": "check",
  "config_path": "pyproject.toml",
  "checked": 1,
  "changed": [],
  "diagnostics": [
    {
      "path": "src/example.py",
      "line": 1,
      "column": 1,
      "code": "LMH004",
      "message": "copyright year ends at 2025; expected 2026",
      "fixable": true
    }
  ],
  "expected_header": "# Copyright (C) <FILE_CREATION_YEAR>-2026, Example Organization.\n...",
  "error": null
}
```

| Code | Meaning |
| --- | --- |
| `LMH001` | Missing header |
| `LMH002` | Owner mismatch |
| `LMH003` | Invalid, reversed, future, or out-of-policy year |
| `LMH004` | Recognized stale year; repairable only when `fixable` is true |
| `LMH005` | Missing/mismatched license notice |
| `LMH006` | Malformed, misplaced, duplicated, or ambiguous layout |
| `LMH007` | Unsupported encoding or invalid bytes |
| `LMH008` | Unsafe or concurrently changed repair target |
| `LMH900` | Command/configuration/I/O error, in `error` rather than `diagnostics` |

Copy this instruction into an agent task:

```text
Read the declared owner, starting year, license, and paths; ask if any are missing.
Run lmh check --output-format json. Exit 1 means findings; exit 2 means stop.
Only run lmh fix when source changes are authorized, then recheck and inspect the
targeted diff. Never infer legal facts or install, commit, or push without permission.
```

The optional [agent skill](.agents/skills/lint-my-headers/SKILL.md) uses this same contract. Its retained model-evaluation results are historical Python-era evidence, not Rust evaluations.

## Integrations

For pre-commit or [prek](https://github.com/j178/prek), install the release wheel in the hook's isolated Python 3.11+ environment. `--only-binary` prevents an unexpected Rust build:

```yaml
repos:
  - repo: local
    hooks:
      - id: lmh
        name: Lint My Headers
        entry: lmh check
        language: python
        types: [python]
        additional_dependencies:
          - --only-binary=lint-my-headers
          - lint-my-headers==0.6.0
```

To test an unreleased checkout instead, the first-party source hook remains available:

```yaml
repos:
  - repo: https://github.com/frgfm/lint-my-headers
    rev: <TAG_OR_IMMUTABLE_SHA>
    hooks:
      - id: lmh
```

The source hook compiles Rust on first installation with the pinned toolchain. Pre-commit's Rust installer does not pass `--locked`; the Action's source mode does.

Pull-request CI can run the same hook or the [GitHub Action](action.yml):

```yaml
steps:
  - uses: actions/checkout@v7
  - uses: frgfm/lint-my-headers@v0.6.0
```

The Action reads repository policy; its documented inputs override it. By default it uses uv to install the exact PyPI version declared by the Action ref, with source builds disabled. `version: '0.6.0'` can select an exact published version; `version: source` explicitly builds the checked-out Action code using `Cargo.lock`. Floating versions, missing releases, and unavailable wheels fail rather than falling back to a compiler. Prefer immutable release SHAs; the v0.6.0 release notes provide its commit SHA. Use source mode for local/unreleased refs.

Action outputs are compact JSON arrays: `issues` contains unresolved paths; `changed` contains completed writes. On exit 2, `issues` stays `[]`, while `changed` retains any completed repairs.

The optional [January 1 workflow](.github/workflows/update-copyright-years.yml) opens or updates one reviewable year-refresh PR. It never writes directly to protected `main`.

## Maintenance

See [CONTRIBUTING.md](CONTRIBUTING.md) for checks and [RELEASE_NOTES.md](RELEASE_NOTES.md) for the breaking rename and publication gates. Runtime logic is Rust; the Python package contains only launchers and source data. Licensed under [Apache-2.0](LICENSE).
