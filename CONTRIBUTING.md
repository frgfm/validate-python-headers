# Contributing to Lint My Headers

Follow the [code of conduct](CODE_OF_CONDUCT.md), [runtime contracts](README.md), and [contributor safety rules](AGENTS.md).

## Structure

- `rust/analysis.rs`: header recognition and proposed year replacements.
- `rust/filesystem.rs`: discovery, identity checks, and atomic writes.
- `rust/config.rs`, `rust/lib.rs`: configuration, command execution, and output.
- `tests/cli.rs` and Rust module tests: CLI and safety regression coverage.
- `src/lint_my_headers`: optional Python launcher and pinned SPDX source data.
- `src/tests`, `.github/`, `scripts/`: release checks and maintainer tooling.
- `.agents/skills/lint-my-headers`: agent instructions and historical eval assets.

## Local development

Use the Rust toolchain pinned in `rust-toolchain.toml`, a C compiler for Tree-sitter, Python 3.11+, and uv. Work on a feature branch.

```shell
make install-quality
make test
make quality
make package-check
uv run --no-sync --group quality prek run --all-files
uv run --no-sync --group quality prek try-repo . lmh --all-files
git diff --check
```

`make style` applies formatting fixes. Review its diff. `make spdx-check` verifies the exact pinned snapshot and generated legacy compatibility data; use `python scripts/update_spdx_licenses.py --help` for deliberate updates.

Keep regressions covered at the layer that owns the behavior. Preserve read-only checks, year-only repairs, all other bytes/mode, link/race refusal, JSON, exit codes, and Action outputs. Never infer legal ownership or licensing.

Report reproducible problems through [issues](https://github.com/frgfm/lint-my-headers/issues). Pull requests should describe changed behavior, checks run, and unverified platform/release gates. Publication and repository mutations follow the owner-controlled checklist in [RELEASE_NOTES.md](RELEASE_NOTES.md).
