# Validate Python headers

<p align="center">
  <a href="https://github.com/frgfm/validate-python-headers/actions/workflows/tests.yml">
    <img alt="CI" src="https://img.shields.io/github/actions/workflow/status/frgfm/validate-python-headers/tests.yml?branch=main&label=CI&logo=github&style=flat-square">
  </a>
  <img alt="Latest release" src="https://img.shields.io/github/v/release/frgfm/validate-python-headers?style=flat-square">
  <img alt="License" src="https://img.shields.io/github/license/frgfm/validate-python-headers?style=flat-square">
</p>

## Keep the license with the work

`validate-python-headers` keeps Python files connected to the copyright owner and license your project declares—from local development through pull requests and distribution. It catches missing or stale notices when code changes and opens a reviewable annual pull request for year updates.

- **Keep attribution visible:** check every changed Python file before it leaves a developer's machine.
- **Keep license terms close to the code:** help contributors and downstream users see which declared terms apply.
- **Automate maintenance:** refresh recognized copyright years once a year without pushing directly to the default branch.

The tool enforces the policy you configure. It does not determine ownership, choose the legally appropriate license, prove compliance, or replace legal advice.

## Quick start

### 1. Configure once

Add the policy to `pyproject.toml`:

```toml
[tool.validate-python-headers]
owner = "YOUR NAME OR ORGANIZATION"
starting-year = 2022
license = "Apache-2.0"
paths = ["src", "tests"]
ignore-files = ["__init__.py"]
ignore-folders = [".github"]
```

Use `license-notice = ".github/license-notice.txt"` instead of `license` when the repository has a custom notice. Configure exactly one of them.

The CLI finds the nearest `pyproject.toml`. Command-line options override it, and explicit file or directory arguments override `paths`.

### 2. Check files before every commit

Add the first-party hook to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/frgfm/validate-python-headers
    rev: v0.6.0
    hooks:
      - id: validate-python-headers
```

Install the hook and establish a clean baseline:

```console
pre-commit install
pre-commit run validate-python-headers --all-files
```

After that, pre-commit supplies only staged Python files to the CLI. Use a released tag such as `v0.6.0`, or pin the immutable commit SHA recorded for that release. Do not pin `main`.

### 3. Check changed files on every pull request

Add `.github/workflows/headers.yml`:

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
      - uses: actions/setup-python@v7
        with:
          python-version: '3.11'
      - run: python -m pip install pre-commit
      - name: Check changed Python files
        env:
          BASE_SHA: ${{ github.event.pull_request.base.sha }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha }}
        run: pre-commit run validate-python-headers --from-ref "$BASE_SHA" --to-ref "$HEAD_SHA"
```

This uses pre-commit's documented [`--from-ref` and `--to-ref` CI workflow](https://pre-commit.com/#usage-in-continuous-integration), so local and pull-request checks select files the same way. Deleted files are naturally excluded.

## Open an annual copyright update pull request

The pull-request check stays focused on changed files. The annual job is the deliberate full-project sweep.

Add `.github/workflows/update-copyright-years.yml` and customize the branch name if needed:

```yaml
name: update copyright years

on:
  workflow_dispatch:
  schedule:
    - cron: "1 0 1 1 *"
      timezone: Europe/Paris

permissions:
  contents: write
  pull-requests: write

jobs:
  update:
    runs-on: ubuntu-latest
    env:
      TZ: Europe/Paris
      BRANCH_NAME: automation/update-copyright-years
      BASE_BRANCH: ${{ github.event.repository.default_branch }}
    steps:
      - uses: actions/checkout@v7
        with:
          ref: ${{ github.event.repository.default_branch }}
          fetch-depth: 0
      - uses: actions/setup-python@v7
        with:
          python-version: '3.11'
      - name: Install the released CLI
        run: >-
          python -m pip install
          "validate-python-headers @ git+https://github.com/frgfm/validate-python-headers.git@v0.6.0"
      - name: Refresh recognized copyright years
        run: validate-python-headers fix
      - name: Open or update the annual pull request
        shell: bash
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          if git diff --quiet -- ':(glob)**/*.py'; then
            echo "Copyright years are already current."
            exit 0
          fi

          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          expected_sha="$(git ls-remote --heads origin "$BRANCH_NAME" | cut -f1)"
          git switch -C "$BRANCH_NAME"
          git add -- ':(glob)**/*.py'
          git commit -m "chore: update copyright years for $(date +%Y)"

          if test -n "$expected_sha"; then
            git push --force-with-lease="refs/heads/$BRANCH_NAME:$expected_sha" origin "HEAD:refs/heads/$BRANCH_NAME"
          else
            git push --set-upstream origin "$BRANCH_NAME"
          fi

          pr_number="$(gh pr list --base "$BASE_BRANCH" --head "$BRANCH_NAME" --state open --json number --jq '.[0].number // empty')"
          if test -n "$pr_number"; then
            gh pr edit "$pr_number" --title "chore: update copyright years" --body "Automated annual refresh of recognized Python copyright years."
          else
            gh pr create --base "$BASE_BRANCH" --head "$BRANCH_NAME" --title "chore: update copyright years" --body "Automated annual refresh of recognized Python copyright years."
          fi
```

GitHub supports [IANA timezones for scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule). Setting both the schedule timezone and `TZ` ensures the CLI observes the new year at local midnight.

The workflow exits successfully without creating an empty pull request when every header is current. A pull request created with `GITHUB_TOKEN` starts its checks in an approval-required state; a maintainer can approve them, or the workflow can use a GitHub App or PAT when automatic execution is required. See GitHub's documentation on [triggering a workflow from a workflow](https://docs.github.com/en/actions/how-tos/writing-workflows/choosing-when-your-workflow-runs/triggering-a-workflow#triggering-a-workflow-from-a-workflow).

## CLI reference

Install directly from a released Git tag:

```console
python -m pip install "validate-python-headers @ git+https://github.com/frgfm/validate-python-headers.git@v0.6.0"
```

Check or fix the configured project paths:

```console
validate-python-headers check
validate-python-headers fix
```

Pass files or directories to narrow one invocation:

```console
validate-python-headers check src/changed.py tests/
validate-python-headers fix src/changed.py
```

For a one-off repository without configuration, pass `--owner`, `--starting-year`, and either `--license` or `--license-notice` after the command. `--config` selects a specific `pyproject.toml`.

| Exit code | Meaning |
| --- | --- |
| `0` | Every selected file is valid. |
| `1` | One or more selected files still have invalid headers. |
| `2` | Configuration, path, license, or I/O error. |

## GitHub Action compatibility

Existing Action workflows remain supported. When the repository has `[tool.validate-python-headers]`, no duplicated policy inputs are required:

```yaml
- uses: actions/checkout@v7
- uses: frgfm/validate-python-headers@v0.6.0
```

Every existing input remains available as an override:

```yaml
- uses: frgfm/validate-python-headers@v0.6.0
  with:
    owner: 'YOUR NAME OR ORGANIZATION'
    starting-year: 2022
    license: 'Apache-2.0'
    folders: 'src,tests'
    ignore-files: '__init__.py'
    mode: check
```

The `issues` output is a compact JSON array of invalid paths and is `[]` on success:

```json
["src/missing.py","src/wrong_owner.py"]
```

## Conservative fix behavior

`fix` only refreshes an existing copyright line for the configured owner:

```text
# Copyright (C) YYYY, OWNER.
# Copyright (C) YYYY-YYYY, OWNER.
```

It preserves the original start year. A stale single year becomes `START-CURRENT` and a stale range receives the current end year. Already-current notices remain byte-for-byte unchanged.

The CLI deliberately does not invent or normalize headers. Missing headers, malformed or reversed years, future years, owner mismatches, and unknown license text remain unchanged and fail the command after all safe repairs have been attempted.

Safe repairs preserve the shebang, encoding/BOM, newline style, file permissions, license notice, and every non-copyright byte.

## Troubleshooting

### The first all-files check fails

Review the reported paths and the example header printed once at the end. `fix` can refresh recognized stale years, but missing or ambiguous headers require a human decision.

### Configuration fails before files are checked

The error names the exact `[tool.validate-python-headers]` key and expected type. Confirm that `owner` and `starting-year` exist, exactly one license source is configured, and every path is relative to the configuration file.

### The annual pull request checks are waiting

Approve the workflow run in the pull request. This approval boundary is GitHub's default behavior for pull requests created or updated with `GITHUB_TOKEN`.

## Runtime and migration

The CLI requires Python 3.11 or newer and has no runtime package dependencies. GitHub-hosted Ubuntu runners provide Python, while the examples pin Python 3.11 for a reproducible floor.

Version 0.6.0 replaces the Docker runtime with a direct Python CLI and composite Action. Existing release tags remain unchanged. Install or reference an owner-controlled `v0.6.0` tag or immutable release SHA after it is published.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Distributed under the Apache License 2.0. See [LICENSE](LICENSE).
