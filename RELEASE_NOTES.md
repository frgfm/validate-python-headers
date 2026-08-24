# Lint My Headers v0.6.0

`validate-python-headers` is now **Lint My Headers**. This is an intentional clean break before the first PyPI publication.

## Required migration

GitHub does not redirect Action calls after a repository rename. Every old reference will fail with `repository not found` and must be changed:

```diff
- uses: frgfm/validate-python-headers@v0.5.1
+ uses: frgfm/lint-my-headers@v0.6.0
```

For security-sensitive workflows, use the immutable v0.6.0 release commit SHA instead of the tag.

| Before | v0.6.0 |
| --- | --- |
| repository and Action `frgfm/validate-python-headers` | `frgfm/lint-my-headers` |
| command `vph` | `lmh` |
| command `validate-python-headers` | `lint-my-headers` |
| configuration `[tool.validate-python-headers]` | `[tool.lint-my-headers]` |
| Python module `validate_headers` | `lint_my_headers` |
| diagnostics without stable codes | `LMH001`–`LMH008`, `LMH900` |

No legacy aliases or redirect PyPI package are provided. The historical PyPI name remains unclaimed by design.

## Highlights

- PyPI wheel and source distribution with no runtime dependency.
- Stable JSON schema version 1 for coding agents and CI.
- One deterministic diagnostic per unresolved file.
- Python-aware BOM, shebang, and PEP 263 encoding handling.
- Conservative stale-year repair with symlink, reparse-point, hard-link, and concurrent-change protection.
- SPDX License List Data v3.28.0 with compatibility for every notice accepted from the previous v3.17 snapshot.
- First-party pre-commit/prek hook and composite Action with `issues` and `changed` outputs.

v0.6.0 supports Python source files. The broader name does not promise additional source languages in this release.

## Owner-controlled release gates

- [ ] Recheck the PyPI, repository, and Marketplace names.
- [ ] Delist historical Marketplace releases without deleting tags.
- [ ] Merge the implementation while the old repository path still exists.
- [ ] Rename the repository to `lint-my-headers` and update its description/topics.
- [ ] Configure the protected GitHub `pypi` environment and matching pending PyPI Trusted Publisher.
- [ ] Publish and verify `v0.6.0rc1` on live PyPI and through the remote Action.
- [ ] Publish final `v0.6.0` only from a passing RC.
- [ ] Update user-controlled downstream repositories to the immutable final SHA.

If PyPI accepts only part of an upload, rerun the failed `publish` and `verify` jobs against the retained `distributions` artifact. Do not rerun `build`; the workflow refuses a same-named remote file whose SHA-256 differs.
