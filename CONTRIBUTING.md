# Contributing to lint-my-headers

Contributions are welcome. Follow the [code of conduct](CODE_OF_CONDUCT.md) and preserve the compatibility and mutation guarantees below.

## Codebase structure

- `rust/analysis.rs` owns header analysis and byte-preserving year replacements.
- `rust/filesystem.rs` owns discovery, identity checks, and atomic writes.
- `rust/config.rs` and `rust/lib.rs` own configuration, CLI execution, and JSON/Action outputs.
- `tests/cli.rs` exercises compiled binaries; Rust module tests cover internal safety behavior.
- `src/lint_my_headers` contains only the optional Python launcher and embedded SPDX source data.
- `src/tests` contains tests for Python release-maintenance helpers.
- `action.yml` is the compatible composite GitHub Action wrapper.
- `.github/workflows` covers CI, annual review pull requests, and artifact publication.

Keep these boundaries boring. The project does not need a generic rule engine, plugin API, or second parser in an integration.

## Compatibility and safety rules

- Rust 1.93 is the build toolchain; the optional Python launcher supports Python 3.11+.
- `check` never writes source files.
- `fix` changes only one recognized stale year for the configured owner.
- Missing, malformed, ambiguous, future-dated, wrong-owner, and wrong-license headers remain unchanged.
- Repairs preserve Python preambles, encodings, newlines, file mode, and every non-year byte.
- Repairs fail closed for symlinks, reparse points, symlinked parents, hard links, and content races.
- Keep CLI, JSON, `pyproject.toml`, pre-commit/prek, Action inputs/outputs, README examples, and tests aligned.
- Preserve exit codes `0` clean, `1` findings, and `2` command/configuration/I/O error.
- Never infer legal ownership or license choices from Git history or neighboring files.

## Local setup

Fork and clone the repository, then create a branch rather than working on `main`:

```console
git clone git@github.com:<YOUR_GITHUB_ACCOUNT>/lint-my-headers.git
cd lint-my-headers
git remote add upstream https://github.com/frgfm/lint-my-headers.git
git checkout -b a-short-description
make install-quality
```

## Verification

Run Rust tests and optimized-mode Python release-helper tests:

```console
make test
```

Run formatting, lint, typing, and dependency checks without modifying files:

```console
make quality
```

Apply supported formatting fixes:

```console
make style
```

Build and smoke-test the installable artifacts when package behavior changes:

```console
make package-check
uv run --no-sync --group quality prek try-repo . lmh --all-files
```

Verify the vendored SPDX data after deliberately refreshing it:

```console
python scripts/update_spdx_licenses.py \
  --baseline-ref 94972478f38d080eadd37f098f771eb4cd235ae4 \
  --baseline-sha256 d557d74124ce6b367efd161e7b53ab1743ad45e302c3476bfb0988ee67b766e0 \
  --spdx-tag v3.28.0 \
  --expected-sha256 f728c534d8bd1044fc515a2ddb2292be99559021d830bfa3281be0bcd36302ee \
  --check
```

Do not publish packages, tags, releases, branches, or pull requests as part of ordinary verification.

## Feedback and pull requests

Use [issues](https://github.com/frgfm/lint-my-headers/issues) for reproducible bugs and feature requests. Use [discussions](https://github.com/frgfm/lint-my-headers/discussions) for usage questions.

Push your focused branch, open a pull request, and complete the repository template. Include the exact checks you ran and any release-only or platform-specific gate that remains open.
