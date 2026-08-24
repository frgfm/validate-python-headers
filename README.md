# Lint My Headers

<p align="center">
  <a href="https://github.com/frgfm/lint-my-headers/actions/workflows/tests.yml">
    <img alt="CI" src="https://img.shields.io/github/actions/workflow/status/frgfm/lint-my-headers/tests.yml?branch=main&label=CI&logo=github&style=flat-square">
  </a>
  <a href="https://pypi.org/project/lint-my-headers/">
    <img alt="PyPI" src="https://img.shields.io/pypi/v/lint-my-headers?style=flat-square">
  </a>
  <a href="https://github.com/frgfm/lint-my-headers/blob/main/LICENSE">
    <img alt="License" src="https://img.shields.io/github/license/frgfm/lint-my-headers?style=flat-square">
  </a>
</p>

`lint-my-headers` is agent-ready license-header linting for source code, starting with Python. It checks every selected file against one project policy, explains each failure with a stable diagnostic, and safely updates only recognized stale copyright years.

It does not choose a license, provide legal advice, insert missing headers, or claim full SPDX/REUSE compliance.

## Quick start

Install the command as a tool:

```shell
uv tool install lint-my-headers
```

Declare the policy once in `pyproject.toml`:

```toml
[tool.lint-my-headers]
owner = "Example Organization"
starting-year = 2024
license = "Apache-2.0"
paths = ["src", "tests"]
ignore-files = ["version.py"]
ignore-folders = ["src/generated"]
```

Then check it:

```shell
lmh check
```

A valid file looks like:

```python
# Copyright (C) 2024-2026, Example Organization.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

value = 1
```

Failures point to one primary problem per file:

```text
src/example.py:1:1: LMH004 copyright year ends before 2026 [fixable]
```

Use the long command without installing:

```shell
uvx --from lint-my-headers lint-my-headers check
```

## Commands

| Command | Behavior |
| --- | --- |
| `lmh check` | Reports findings and never writes source files. |
| `lmh fix` | Updates only a recognized stale year on a safe regular file, then reparses it. |
| `lmh --version` | Prints the installed distribution version. |

Both `lmh` and `lint-my-headers` are first-party entry points. Commands return `0` when clean, `1` for findings, and `2` for invocation, configuration, or I/O failures.

Explicit files or folders override configured `paths`:

```shell
lmh check src/package tests/test_package.py
```

CLI policy options override `pyproject.toml`. `--config` selects a specific configuration file.

## Stable JSON for coding agents

Put `--output-format` after `check` or `fix`:

```shell
lmh check --output-format json
```

JSON is the only stdout in this mode:

```json
{
  "changed": [],
  "checked": 1,
  "command": "check",
  "config_path": "pyproject.toml",
  "diagnostics": [
    {
      "code": "LMH004",
      "column": 1,
      "fixable": true,
      "line": 1,
      "message": "copyright year ends before 2026",
      "path": "src/example.py"
    }
  ],
  "error": null,
  "expected_header": "# Copyright (C) <FILE_CREATION_YEAR>-2026, Example Organization.\n...",
  "schema_version": 1,
  "tool_version": "0.6.0"
}
```

The diagnostic codes are stable within schema version 1:

| Code | Meaning | Automatically repairable |
| --- | --- | --- |
| `LMH001` | Missing legal header | No |
| `LMH002` | Copyright owner mismatch | No |
| `LMH003` | Invalid, reversed, future, or out-of-policy year | No |
| `LMH004` | Recognized stale year | Only on a safe file |
| `LMH005` | Missing or mismatched license notice | No |
| `LMH006` | Malformed, misplaced, duplicated, or ambiguous layout | No |
| `LMH007` | Python source encoding cannot be decoded | No |
| `LMH008` | Repair target is unsafe or changed during repair | No |
| `LMH900` | Configuration, selected-path, I/O, or runtime failure | No |

### Copy-paste instruction for a coding agent

```text
Integrate lint-my-headers without guessing legal facts. Read the repository's owner,
starting year, license, and selected Python paths; ask me if any are missing. Add one
[tool.lint-my-headers] table, then run `lmh check --output-format json`. Treat exit 1
as findings and exit 2 as an integration error. Do not run `lmh fix` unless I explicitly
authorize source mutations. After an authorized fix, rerun check and inspect only the
targeted diff. Do not install, commit, push, or open a pull request without permission.
```

## Pre-commit and prek

```yaml
repos:
  - repo: https://github.com/frgfm/lint-my-headers
    rev: v0.6.0
    hooks:
      - id: lmh
```

Run it with either pre-commit or [prek](https://github.com/j178/prek):

```shell
uvx --from prek prek run lmh --all-files
```

The first-party hook intentionally selects Python files. Additional source languages are not part of v0.6.

## GitHub Action

Configuration-first usage avoids duplicating policy in workflow YAML:

```yaml
steps:
  - uses: actions/checkout@v7
  - uses: frgfm/lint-my-headers@v0.6.0
```

Every policy input remains available when a repository cannot use `pyproject.toml`:

```yaml
- uses: frgfm/lint-my-headers@v0.6.0
  with:
    mode: check
    owner: Example Organization
    starting-year: 2024
    license: Apache-2.0
    folders: src,tests
    ignore-files: version.py
    ignore-folders: src/generated
```

The Action always exposes compact JSON outputs:

- `issues`: sorted unresolved paths;
- `changed`: sorted paths actually written by `fix`.

For compatibility, `issues` is `[]` on exit `2`; `changed` still lists writes completed before a later I/O failure.

For supply-chain-sensitive workflows, replace the version tag with the immutable commit SHA from the release.

## Policy and file semantics

| Key | Required | Meaning |
| --- | --- | --- |
| `owner` | Yes | Exact single-line copyright owner. |
| `starting-year` | Yes | Earliest allowed creation year. |
| `license` | One license source | SPDX license identifier selecting the bundled prose notice. |
| `license-notice` | One license source | Project-relative custom notice file. |
| `paths` | No | Project-relative files or folders; default `.`. |
| `ignore-files` | No | Exact filenames ignored everywhere; default `__init__.py`. |
| `ignore-folders` | No | Project-relative subtrees ignored everywhere; default `.github`. |

- Configuration paths are relative to the selected `pyproject.toml`; explicit CLI paths are relative to the invocation directory.
- Output paths are sorted, project-root-relative, and use `/`. An explicitly selected external path may begin with `..`.
- A UTF-8 BOM, any first-line shebang beginning `#!`, and valid PEP 263 encoding cookies are recognized before the legal header.
- `check` may inspect an explicitly selected symlinked file, but `fix` refuses symlinks, symlinked parents, reparse points, and multi-link inodes.
- Directory discovery never follows symlink or reparse-point directories.
- `fix` preserves every byte outside the stale year, preserves file mode, validates the repaired bytes, and fails closed if the file changes during repair.

The bundled license list is the exact SPDX License List Data v3.28.0 snapshot. Previously accepted v3.17 notice names and URLs remain valid, including removed legacy identifiers, but compound SPDX expressions and new exception semantics are not introduced.

## Annual year refresh

The January 1 workflow is optional. This repository's tested implementation is [`.github/workflows/update-copyright-years.yml`](https://github.com/frgfm/lint-my-headers/blob/main/.github/workflows/update-copyright-years.yml). It opens or updates one reviewable pull request; it does not push protected `main`.

## v0.6 migration

v0.6 is an intentional identity break:

- repository and Action: `frgfm/lint-my-headers`;
- distribution: `lint-my-headers`;
- commands: `lmh`, `lint-my-headers`;
- configuration: `[tool.lint-my-headers]`;
- Python module: `lint_my_headers`;
- diagnostics: `LMH...`.

There are no `vph`, `validate-python-headers`, `[tool.validate-python-headers]`, or `validate_headers` aliases. GitHub does not redirect Action calls after a repository rename, so old `uses:` references must be updated. The historical `validate-python-headers` name was never published on PyPI and remains unclaimed by design.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for local checks and release boundaries. The runtime remains standard-library-only and supports Python 3.11 through 3.14.

## License

Distributed under the Apache License 2.0. See [LICENSE](LICENSE).
