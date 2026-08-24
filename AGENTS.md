# Contributor guidance

`lint-my-headers` is a standard-library Python 3.11+ CLI. Keep changes focused and preserve these public contracts:

- commands `lmh` and `lint-my-headers` with `check` and `fix`;
- configuration `[tool.lint-my-headers]`;
- exits 0 clean, 1 findings, 2 invocation/configuration/I/O failure;
- JSON schema version 1 and `LMH` diagnostic meanings;
- GitHub Action inputs plus `issues` and `changed` outputs.

`check` must never write. `fix` may only update one recognized stale year for the configured owner, must preserve all other bytes and mode, and must refuse ambiguous, symlinked, reparse-point, multi-link, or concurrently changed targets. Never infer an owner, license, starting year, or legal conclusion.

Run before handoff:

```shell
make test
make quality
make package-check
uv run --group quality prek run --all-files
git diff --check
```

PyPI, GitHub releases, Marketplace changes, repository renames, downstream migrations, commits, and pushes require separate explicit authorization.
