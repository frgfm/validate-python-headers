# Contributing to Lint My Headers

Contributions are welcome. Follow the [code of conduct](CODE_OF_CONDUCT.md), search [existing issues](https://github.com/frgfm/lint-my-headers/issues), and keep changes scoped to one observable problem.

## Repository structure

- [`src/lint_my_headers`](https://github.com/frgfm/lint-my-headers/tree/main/src/lint_my_headers): CLI, configuration, diagnostics, and safe repair.
- [`src/tests`](https://github.com/frgfm/lint-my-headers/tree/main/src/tests): standard-library unit and contract tests.
- [`scripts`](https://github.com/frgfm/lint-my-headers/tree/main/scripts): SPDX generation and distribution verification.
- [`action.yml`](https://github.com/frgfm/lint-my-headers/blob/main/action.yml): composite GitHub Action.
- [`.github/workflows`](https://github.com/frgfm/lint-my-headers/tree/main/.github/workflows): CI, annual refresh, and protected publication.

The runtime supports Python 3.11+ and has no third-party dependency. Development commands use the versions pinned in `pyproject.toml` and `uv.lock`.

## Local setup and checks

```shell
git clone git@github.com:<YOUR_GITHUB_ACCOUNT>/lint-my-headers.git
cd lint-my-headers
git remote add upstream https://github.com/frgfm/lint-my-headers.git
git switch -c a-short-description
make install-quality
```

Run the release-relevant local gates:

```shell
make test
make quality
make package-check
uv run --group quality prek run --all-files
git diff --check
```

`make style` applies Ruff fixes and formatting. Review the resulting diff before committing.

## Compatibility and safety

- Preserve the CLI, JSON schema, diagnostic meanings, exit codes, and Action inputs/outputs documented in the README.
- `check` must not write.
- `fix` may only repair a recognized stale copyright year and must remain atomic, byte-preserving outside that year, idempotent, and fail-closed on unsafe targets.
- Do not infer an owner, license, starting year, or legal conclusion.
- Update the SPDX snapshot only with `scripts/update_spdx_licenses.py`; the checksum and generated compatibility data are part of the review.

## Pull requests and releases

Use a conventional commit title and explain the behavior changed, checks run, and any unperformed live gate. Push your branch and open a pull request against `main`.

PyPI publication, GitHub releases, Marketplace publication, repository settings, and downstream migrations are owner-controlled operations. A green local or pull-request build does not claim those live gates passed.
