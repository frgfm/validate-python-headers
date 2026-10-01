# Lint My Headers

A Rust CLI that checks Python, JavaScript, TypeScript, and Rust copyright/license headers and safely refreshes recognized stale years. It never chooses ownership or licensing, inserts missing headers, or claims legal/SPDX/REUSE compliance.

## Quick start

Install a published release, or build this checkout with Rust 1.93 and a C compiler. Multilingual support requires this checkout until a release includes it:

```shell
uv tool install lint-my-headers
# From source:
cargo build --release --locked
```

PyPI wheels contain native `lmh` and `lint-my-headers` executables; source distributions require Rust and a C compiler for the bundled Tree-sitter grammars. Python 3.11+ is needed only for PyPI tooling and the optional launchers. `python -m lint_my_headers` replaces Python with the native process on Unix; Windows starts a child process. The callable `main(argv)` always returns the child's exit code. No Node.js runtime is needed.

Declare the policy in `.lmh.toml`:

```toml
owner = "Example Organization"
starting-year = 2024
license = "Apache-2.0"
languages = ["python", "javascript", "typescript", "rust"]
paths = ["src", "tests"]
ignore-files = ["version.py"]
ignore-folders = ["src/generated"]
```

```shell
lmh check                              # Read-only; configured paths
lmh check src/package tests/test_api.py # Explicit paths
lmh fix                                # Safe stale-year repairs only
lmh check --languages typescript       # Override the configured language list
lmh --version
lmh check --help
```

A valid header in 2026:

```python
# Copyright (C) 2024-2026, Example Organization.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.
```

JavaScript, TypeScript, and Rust use the exact same text and blank lines with `//` in place of `#`. Custom `license-notice` files may contain plain text; existing Python-commented notices remain accepted. Missing headers are never inserted.

Diagnostics name the location, reason, and repair eligibility:

```text
src/example.py:1:1: LMH004 copyright year ends at 2025; expected 2026 [fixable]
```

Exit codes: **0** clean, **1** unresolved findings, **2** invocation/configuration/I/O error. `fix` preserves the creation year and changes no other bytes. Unknown, missing, malformed, duplicate, wrong-owner, or future-dated headers require manual review.

## Configuration and safety

CLI policy options override configuration; `--config` selects an exact file. Otherwise discovery searches upward from the invocation directory, choosing the nearest applicable configuration. In each directory, priority is `.lmh.toml`, `pyproject.toml`, `Cargo.toml`, then `package.json`. Manifests without LMH settings are skipped. Invalid configurations fail; configurations are never merged.

Use top-level settings in `.lmh.toml`, `[tool.lint-my-headers]` in `pyproject.toml`, `[package.metadata.lint-my-headers]` or `[workspace.metadata.lint-my-headers]` in `Cargo.toml` (package settings take precedence), or a `"lint-my-headers"` object in `package.json`. Other explicit TOML filenames use the `[tool.lint-my-headers]` form. The same keys and explicit policy apply in every container. Configured paths are relative to that file; explicit CLI paths are relative to the invocation directory.

| Key / CLI option | Meaning and default |
| --- | --- |
| `owner` / `--owner` | Required exact single-line copyright owner. |
| `starting-year` / `--starting-year` | Required earliest accepted file creation year. |
| `license` / `--license` | SPDX identifier selecting a prose notice; requires local `LICENSE`. |
| `license-notice` / `--license-notice` | Custom notice file; configure exactly one license source. |
| `paths` / positional paths | Selected files or directories; default `.`. |
| `languages` / `--languages` | Non-empty allowlist: `python`, `javascript`, `typescript`, `rust`; default `["python"]`. CLI values are comma-separated and replace the configured list. |
| `ignore-files` / `--ignore-files` | Exact basenames; default `__init__.py`. |
| `ignore-folders` / `--ignore-folders` | Excluded subtrees; default `.github`. |

CLI ignore lists are comma-separated; configuration lists are TOML arrays. Exclusions also apply to explicit inputs. Diagnostics use sorted, project-relative `/` paths, including `..` for explicitly selected external files.

Only enabled, supported extensions are checked, including explicit files: Python `.py`; JavaScript `.js`, `.jsx`, `.mjs`, `.cjs`; TypeScript `.ts`, `.tsx`, `.mts`, `.cts`, including declaration variants; Rust `.rs`. This changes earlier explicit-file behavior: other extensions and extensionless shebang scripts are skipped. Limit `paths` or exclude dependency/build directories such as `node_modules`, `target`, and `.build`; ignored subtrees are not traversed. Unknown language names and empty language lists fail.

Python shebangs, UTF-8 BOMs, and PEP 263 cookies are preserved. Verified encodings are UTF-8, ASCII, Latin-1, and Windows-1252; other codecs fail without repair. Ambiguous newer Python string syntax also fails closed.

JavaScript/TypeScript support UTF-8 and `//` headers, preserving BOMs, shebangs, CRLF, and the body. Tree-sitter distinguishes real comments from strings, templates, regex literals, and JSX. Parse errors and copyright-bearing block comments fail closed. A shebang must be followed by a blank line before the header; bare CR headers are refused.

Rust uses the same UTF-8, BOM, newline, and year-only repair rules. Its grammar distinguishes comments from raw/byte strings, character literals, lifetimes, macros, and nested block comments. Use ordinary `//` headers; copyright-bearing block/doc comments and parse errors refuse repair. Crate attributes such as `#![allow(...)]` belong after the header. Shebangs require a blank separator; ambiguous comment-prefixed `#!` forms are refused.

For a Rust package, put the policy in `Cargo.toml`:

```toml
[package.metadata.lint-my-headers]
owner = "Example Organization"
starting-year = 2024
license = "Apache-2.0"
languages = ["rust"]
paths = ["src", "tests"]
ignore-folders = ["target"]
```

For a virtual workspace, use `[workspace.metadata.lint-my-headers]` instead, with paths relative to the workspace manifest. Run `lmh check` or `lmh fix`; `--config Cargo.toml` selects that policy explicitly when a higher-priority configuration is present. Package metadata takes precedence over workspace metadata in the same manifest; policy is never inferred from Cargo's package author/license fields.

Directory discovery skips symlinks/reparse points. Explicit linked files may be checked, but repairs refuse symlinks, linked parents, reparse points, and multiple hard links. Before atomic replacement, file identity and contents are revalidated; the repaired bytes must pass the same parser.

The bundled SPDX snapshot is v3.28.0. All previously accepted v3.17 names/URLs remain valid, including the legacy `KiCad-libraries-exception`. Compound SPDX expressions and new exception semantics are unsupported.

## Agents and JSON

Use `lmh check --output-format json`. Successfully parsed JSON-mode commands write only JSON to stdout; malformed CLI syntax remains a stderr usage error.

The schema remains version 1. `expected_header` uses the first enabled language's comment marker; its text and blank lines are shared across all languages.

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

For pre-commit or [prek](https://github.com/j178/prek), the published 0.6.0 wheel supports Python and policy in `pyproject.toml`. Install it in the hook's isolated Python 3.11+ environment; `--only-binary` prevents an unexpected Rust build. Use the source hook below for multilingual support until a release includes it:

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

### Annual copyright refresh

Schedule a review PR for January 1 at **00:01 Europe/Paris**. The scheduler and job use the same timezone so the repair year is January 1's year even while UTC is still December 31. GitHub schedules run from the default branch and can be delayed or dropped under high load; the scheduled minute is not an execution-time guarantee.

First, declare LMH in your project's quality dependencies, then add a `headers-fix` Make target using the same environment as your header check in CI. For a quality dependency group, append the package to the existing group in `pyproject.toml`:

```toml
[dependency-groups]
quality = ["lint-my-headers==0.6.0"]
```

Run `uv lock` and commit the updated `uv.lock`, then add:

```makefile
headers-fix:
	uv run --locked --group quality lmh fix
```

For a quality extra, add the package to `quality` in `[project.optional-dependencies]` and use `uv run --extra quality lmh fix` instead; retain `--locked` when the repository commits its uv lockfile. The target must install/synchronize its environment because scheduled runners start fresh. A global `uv tool install` does not install LMH in the runner's project environment. The LMH version stays in `pyproject.toml`, without a second pin in the workflow.

Save this consumer template as `.github/workflows/update-copyright-years.yml`. This repository's [own workflow](.github/workflows/update-copyright-years.yml) builds its locked Rust source instead of installing a published package; the publication scripts match:

```yaml
name: update copyright years

on:
  schedule:
    - cron: "1 0 1 1 *"
      timezone: Europe/Paris

permissions:
  contents: read

concurrency:
  group: annual-copyright-years
  cancel-in-progress: false

jobs:
  update:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    env:
      TZ: Europe/Paris
      BASE_BRANCH: ${{ github.event.repository.default_branch }}
      UV_PROJECT_ENVIRONMENT: ${{ runner.temp }}/lmh-annual-env
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          ref: ${{ github.event.repository.default_branch }}
          fetch-depth: 0
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          version: "0.12.5"
      - name: Create the annual pull request
        shell: bash
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          set -euo pipefail

          copyright_year="$(date +%Y)"
          branch_name="automation/update-copyright-years-$copyright_year"
          test "$branch_name" != "$BASE_BRANCH"

          pr_number="$(gh pr list --base "$BASE_BRANCH" --head "$branch_name" --state all --json number --jq '.[0].number // empty')"
          if test -n "$pr_number"; then
            echo "Annual pull request #$pr_number already exists."
            exit 0
          fi

          remote_sha="$(git ls-remote --heads origin "$branch_name" | cut -f1)"
          if test -z "$remote_sha"; then
            make headers-fix
            if git diff --quiet -- ':(glob)**/*.py'; then
              echo "Copyright years are already current."
              exit 0
            fi

            git switch -c "$branch_name"
            git config user.name "github-actions[bot]"
            git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
            git add -u -- ':(glob)**/*.py'
            git commit -m "chore: update copyright years for $copyright_year"
            git push --set-upstream origin "$branch_name"
          fi

          gh pr create --base "$BASE_BRANCH" --head "$branch_name" \
            --title "chore: update copyright years for $copyright_year" \
            --body "Annual refresh of recognized Python copyright years using the declared header policy."
```

The external UV environment keeps installed dependency files outside the scan and PR. Repairs follow `[tool.lint-my-headers]` paths/exclusions and update only recognized stale years for its declared owner in supported Python files. They preserve creation years and all other bytes/modes. Missing, ambiguous, unsafe, or wrong-owner notices require manual review; a failed repair stops before any branch or PR is published. To cover more Python source files, extend the declared paths while preserving generated/vendor exclusions. This annual workflow stages Python changes only.

Each year gets one `automation/update-copyright-years-YYYY` branch. Existing PRs, including closed PRs, are left untouched; reopen the existing PR if it was closed by mistake. If a push succeeded but PR creation failed, rerunning resumes PR creation from that branch without overwriting it. If repairs make no changes and no annual branch already exists, no PR is created. Only tracked Python changes are committed; generated untracked files are excluded. Pushes never target the default branch or force-update an existing branch.

Repository setup:

- Merge the policy, Make target and workflow into the default branch. The workflow has only a schedule trigger, so it does not run on pushes, PRs or manual dispatch.
- Enable **Settings → Actions → General → Workflow permissions → Allow GitHub Actions to create and approve pull requests**. The job requests only `contents: write` and `pull-requests: write`; it does not approve or merge its PR.
- PR workflows triggered by `GITHUB_TOKEN` require a writer to click **Approve workflows to run** before their CI starts. Use an existing GitHub App installation token if unattended PR checks are required.
- GitHub disables schedules in public repositories after 60 days without activity; verify the schedule remains enabled before the annual run.

See GitHub's [schedule behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule) and [workflow-token triggering rules](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow#triggering-a-workflow-from-a-workflow).

For a failed scheduled run, fix the cause and use **Actions → Re-run failed jobs** within [30 days of the original run](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs). If no run was created or that window has expired, re-enable a disabled schedule for future runs, then run `make headers-fix` on a fresh branch from the default branch, inspect the diff, and open a manual PR. The workflow has no manual dispatch trigger.

## Maintenance

See [CONTRIBUTING.md](CONTRIBUTING.md) for checks and [RELEASE_NOTES.md](RELEASE_NOTES.md) for the breaking rename and publication gates. Runtime logic is Rust; the Python package contains only launchers and source data. Licensed under [Apache-2.0](LICENSE).
