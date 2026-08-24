# Validate Python headers

<p align="center">
  <a href="https://github.com/frgfm/validate-python-headers/actions/workflows/tests.yml">
    <img alt="CI" src="https://img.shields.io/github/actions/workflow/status/frgfm/validate-python-headers/tests.yml?branch=main&label=CI&logo=github&style=flat-square">
  </a>
  <img alt="PyPI" src="https://img.shields.io/pypi/v/validate-python-headers?style=flat-square">
  <img alt="License" src="https://img.shields.io/github/license/frgfm/validate-python-headers?style=flat-square">
</p>

A dependency-free Python legal-header linter with a conservative copyright-year fixer.

- **Check:** explain exactly why each selected Python file does not match one repository policy.
- **Fix:** refresh only a recognized stale year for the configured owner.
- **Integrate:** reuse the same `pyproject.toml` policy locally, in pre-commit or prek, in CI, and through the compatible GitHub Action.

The tool does not choose a license, determine copyright ownership, provide legal advice, add missing headers, or rewrite ambiguous legal text. Use [REUSE](https://reuse.software/) when you need full multi-file SPDX compliance rather than this deliberately narrow Python workflow.

## Quick start

### 1. Install the CLI from GitHub

Until v0.6.0 is published, install the current release-candidate snapshot directly from GitHub. The full commit SHA keeps the installation reproducible.

With uv:

```console
uv tool install "git+https://github.com/frgfm/validate-python-headers.git@523b1c2fdd7857374999d664aeea9f8809cd497c"
```

Or with pipx:

```console
pipx install "git+https://github.com/frgfm/validate-python-headers.git@523b1c2fdd7857374999d664aeea9f8809cd497c"
```

Both install the primary `vph` command and the longer `validate-python-headers` compatibility alias. Python 3.11 or newer is required.

### 2. Configure one policy

Add this table to the nearest `pyproject.toml`:

```toml
[tool.validate-python-headers]
owner = "YOUR NAME OR ORGANIZATION"
starting-year = 2022
license = "Apache-2.0"
paths = ["src", "tests"]
ignore-files = ["__init__.py"]
ignore-folders = []
```

The corresponding header is:

```python
# Copyright (C) 2022-2026, YOUR NAME OR ORGANIZATION.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.
```

The actual end year is the current year. A file may retain its own start year as long as it is not earlier than `starting-year`.

### 3. Check the repository

```console
vph check
```

Failures use stable, editor-friendly diagnostics:

```text
src/example.py:1:1: VPH004 copyright year ends at 2025; expected 2026 [fixable]
```

Apply only recognized stale-year repairs, then recheck:

```console
vph fix
vph check
```

For example, assuming the current year is 2026, `vph fix` changes this recognized stale header:

```python
# Copyright (C) 2022-2025, YOUR NAME OR ORGANIZATION.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.


def greet():
    return "hello"
```

into:

```python
# Copyright (C) 2022-2026, YOUR NAME OR ORGANIZATION.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.


def greet():
    return "hello"
```

Only the recognized end year changes. Missing or ambiguous headers remain untouched and are reported for manual review.

Pass files or directories to narrow one invocation:

```console
vph check src/changed.py tests/
vph fix src/changed.py
```

## Pre-commit and prek

The first-party hook uses the standard `.pre-commit-config.yaml` format and works with both [pre-commit](https://pre-commit.com/) and [prek](https://prek.j178.dev/):

```yaml
repos:
  - repo: https://github.com/frgfm/validate-python-headers
    rev: 523b1c2fdd7857374999d664aeea9f8809cd497c
    hooks:
      - id: vph
```

For example, with prek:

```console
uv tool install prek
prek install
prek run vph --all-files
```

After the initial baseline, the hook supplies only selected Python files to `vph`.

After v0.6.0 is published, you can replace this snapshot SHA with the `v0.6.0` tag. Do not pin `main`.

## Pull-request checks

This workflow uses prek's changed-file selection so local and CI checks call the same hook:

```yaml
name: headers

on:
  pull_request:

permissions:
  contents: read

jobs:
  headers:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          fetch-depth: 0
      - uses: astral-sh/setup-uv@v10.0.1
        with:
          version: '0.12.5'
      - name: Check changed Python files
        env:
          BASE_SHA: ${{ github.event.pull_request.base.sha }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha }}
        run: uvx --from prek==0.4.14 prek run vph --from-ref "$BASE_SHA" --to-ref "$HEAD_SHA"
```

Pin third-party Actions to immutable SHAs in security-sensitive repositories.

## Annual review pull request

The tested [annual workflow](.github/workflows/update-copyright-years.yml) can run every January 1 or on manual dispatch. It updates one deterministic branch, opens or refreshes one reviewable pull request, and does nothing when no recognized year is stale.

An annual whole-repository year refresh is a project convention, not a universal license or REUSE requirement. Confirm that this policy matches your project before enabling the schedule; [REUSE documents several valid year policies](https://reuse.software/faq/#which-years-do-i-include-in-the-copyright-statement).

## CLI and configuration reference

```console
vph --version
vph check --help
vph fix --help
```

CLI values override `pyproject.toml`. Configuration paths are relative to the configuration file; explicit command-line paths are relative to the invocation directory.

| Setting / option | Required | Default | Meaning |
| --- | --- | --- | --- |
| `owner` / `--owner` | yes | — | Exact, single-line copyright owner. |
| `starting-year` / `--starting-year` | yes | — | Earliest accepted file start year. |
| `license` / `--license` | one license source | — | SPDX license identifier used to select the prose notice. |
| `license-notice` / `--license-notice` | one license source | — | Path to an exact custom notice. |
| `paths` / positional paths | no | `["."]` | Python files or directories to inspect. |
| `ignore-files` / `--ignore-files` | no | `["__init__.py"]` | Exact basenames ignored everywhere, including explicit inputs. |
| `ignore-folders` / `--ignore-folders` | no | `[".github"]` | Exact folder paths ignored, including explicit inputs. |
| `--config` | no | nearest `pyproject.toml` | Select a specific configuration file. |
| `--output-format` | no | `text` | `text` or versioned `json`. |

The repository must contain `LICENSE` when `license` is used. The bundled SPDX License List is v3.28.0; notices previously accepted from the v3.17 snapshot remain valid. The removed `KiCad-libraries-exception` value remains accepted only for that legacy compatibility.

### Diagnostics

| Code | Meaning | Automatically fixable |
| --- | --- | --- |
| `VPH001` | Missing legal header | no |
| `VPH002` | Owner mismatch | no |
| `VPH003` | Invalid, reversed, future, or out-of-policy year | no |
| `VPH004` | Otherwise-valid stale year | safe regular files only |
| `VPH005` | Missing or mismatched license notice | no |
| `VPH006` | Malformed, misplaced, duplicated, or ambiguous layout | no |
| `VPH007` | Python source encoding failure | no |
| `VPH008` | Unsafe repair target | no |

Each invalid file produces one primary diagnostic in `check`. After `fix`, repaired files appear in `changed` and only unresolved files remain in `diagnostics`.

### JSON output

```console
vph check --output-format json
```

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
      "code": "VPH004",
      "message": "copyright year ends at 2025; expected 2026",
      "fixable": true
    }
  ],
  "expected_header": "# Copyright (C) <FILE_CREATION_YEAR>-2026, YOUR NAME OR ORGANIZATION.\n...",
  "error": null
}
```

JSON mode writes only JSON to stdout. Handled configuration, path, license, and I/O errors use the same envelope with `error.code` set to `VPH900`.

| Exit code | Meaning |
| --- | --- |
| `0` | Every selected file is valid. |
| `1` | One or more policy findings remain. |
| `2` | Invocation, configuration, path, license, or I/O error. |

## GitHub Action compatibility

Existing Action workflows remain supported. A configured repository needs no duplicated policy inputs:

```yaml
- uses: actions/checkout@v7
- uses: frgfm/validate-python-headers@v0.6.0
```

Every existing input remains available as an override. The Action exposes compact JSON arrays:

- `issues`: unresolved paths, or `[]` on success and command errors;
- `changed`: paths changed by `fix`, including changes completed before a later I/O error.

## Conservative fix and Python preambles

`fix` updates only one recognized copyright line for the configured owner. It preserves the original start year and changes a stale single year or range to `START-CURRENT`.

The linter understands Python's leading structure: UTF BOM, an arbitrary `#!` shebang, and a valid PEP 263 encoding cookie in line one or two. Repairs preserve the exact preamble, encoding, newline style, file mode, license notice, and every non-year byte.

Missing headers, malformed or duplicate notices, reversed or future years, owner mismatches, and unknown license text remain byte-for-byte unchanged. Repairs also refuse symlinks, reparse points, symlinked parents, multi-link files, and files that change between analysis and replacement.

## AI-agent skill

The repository includes an optional, instruction-only `validate-python-headers` skill. It teaches compatible coding agents to inspect policy, run structured checks, ask rather than infer legal facts, apply only explicitly requested safe fixes, and verify the resulting diff.

For Codex, ask the built-in installer to install the skill from the released repository path:

```text
$skill-installer install the validate-python-headers skill from frgfm/validate-python-headers@v0.6.0
```

The CLI and JSON schema remain authoritative; the skill contains no second parser or formatter.

## Maintainer checks

```console
make test
make quality
python scripts/update_spdx_licenses.py --help
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the complete local workflow.

## Migration from v0.5

v0.6 replaces the Docker runtime with the packaged CLI and direct composite Action. Existing Action inputs remain supported. The undocumented GHCR image is no longer published; existing release tags remain unchanged.

## License

Distributed under the Apache 2.0 License. See [`LICENSE`](LICENSE).
