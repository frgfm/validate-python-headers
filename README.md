# Validate Python headers

<p align="center">
  <a href="https://github.com/frgfm/validate-python-headers/actions/workflows/tests.yml">
    <img alt="CI" src="https://img.shields.io/github/actions/workflow/status/frgfm/validate-python-headers/tests.yml?branch=main&label=CI&logo=github&style=flat-square">
  </a>
  <img alt="Latest release" src="https://img.shields.io/github/v/release/frgfm/validate-python-headers?style=flat-square">
  <img alt="License" src="https://img.shields.io/github/license/frgfm/validate-python-headers?style=flat-square">
</p>

A fast, dependency-free GitHub Action for copyright and license headers in Python repositories.

- **Check:** fail a pull request or push when headers are missing or invalid.
- **Fix:** refresh the years in recognized existing headers, then open a reviewable pull request from a scheduled workflow.

No Docker startup, package install, generated bundle, or external service. The maintained path uses the Python already available on `ubuntu-latest`.

## Check every pull request and commit

Add `.github/workflows/headers.yml`:

```yaml
name: headers

on:
  pull_request:
  push:
    branches: main

permissions:
  contents: read

jobs:
  headers:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: frgfm/validate-python-headers@v0.6.0
        with:
          owner: 'YOUR NAME OR ORGANIZATION'
          starting-year: 2022
          license: 'Apache-2.0'
          folders: 'src,tests'
          ignore-files: '__init__.py'
```

`check` is the default mode and never changes source files. Any invalid file fails the job and is returned in the `issues` output.

Use a released tag such as `v0.6.0`, or pin the immutable commit SHA recorded for that release. Do not pin `main`.

## Open an annual copyright update pull request

Copy the repository's tested [annual workflow](.github/workflows/update-copyright-years.yml) into your repository. It already:

- runs every January 1 and can also be dispatched manually;
- sets both the schedule timezone and `TZ` to avoid the local-midnight/UTC year boundary;
- runs `mode: fix` and does nothing when no tracked Python file changes;
- updates one deterministic branch with an exact-SHA force-with-lease;
- opens or refreshes one pull request instead of pushing to the default branch;
- grants only `contents: write` and `pull-requests: write`.

Customize the owner, license, starting year, folders, and ignore inputs. Replace its local dogfooding reference:

```yaml
uses: ./
```

with the released action:

```yaml
uses: frgfm/validate-python-headers@v0.6.0
```

Pull requests created with the repository `GITHUB_TOKEN` may require a maintainer to trigger or approve checks, depending on repository policy.

## Conservative fix behavior

`fix` only refreshes an existing copyright line for the configured owner:

```text
# Copyright (C) YYYY, OWNER.
# Copyright (C) YYYY-YYYY, OWNER.
```

It preserves the original start year. A stale single year becomes `START-CURRENT` and a stale range receives the current end year. Already-current notices remain byte-for-byte unchanged.

The action deliberately does not invent or normalize headers. Missing headers, malformed or reversed years, future years, owner mismatches, and unknown license text remain unchanged, appear in `issues`, and fail the job after all safe repairs have been attempted.

Safe repairs preserve the shebang, encoding/BOM, newline style, file permissions, license notice, and every non-copyright byte.

## Inputs

| Input | Required | Default | Description |
| --- | --- | --- | --- |
| `owner` | yes | — | Exact copyright owner. |
| `starting-year` | yes | — | Earliest accepted start year for project files. |
| `license` | no | `null` | SPDX license identifier. |
| `folders` | no | `.` | Comma-separated folders to scan. |
| `ignore-files` | no | `__init__.py` | Comma-separated filenames to ignore. |
| `ignore-folders` | no | `.github/` | Comma-separated folders to ignore; pass an empty string to ignore none. |
| `license-notice` | no | `null` | Path to a custom notice, used when `license` is unset. |
| `mode` | no | `check` | `check` or `fix`. |

Specify either `license` or `license-notice`. For a custom notice:

```yaml
- uses: frgfm/validate-python-headers@v0.6.0
  with:
    owner: 'YOUR NAME OR ORGANIZATION'
    starting-year: 2022
    license-notice: '.github/license-notice.txt'
```

## Output

`issues` is a compact JSON array of invalid paths and is `[]` on success:

```json
["src/missing.py","src/wrong_owner.py"]
```

## Runtime

GitHub-hosted Ubuntu runners already provide Python. Self-hosted runners need Python 3.11 or newer available as `python`.

Version 0.6.0 replaces the Docker runtime with this direct composite action and stops publishing the undocumented `ghcr.io/frgfm/validate-python-headers` image. Existing tags remain unchanged. Public code search did not identify image consumers, but private or unindexed consumers may exist.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for local tests and quality checks.

## License

Distributed under the Apache 2.0 License. See [`LICENSE`](LICENSE).
