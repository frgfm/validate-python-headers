# Repository guidance

- Use Python 3.11+ and keep the runtime dependency-free.
- Run `PYTHONOPTIMIZE=1 make test` and `make quality` after behavior changes.
- Keep `validate-python-headers`, `vph`, `python -m validate_headers`, `pyproject.toml`, the pre-commit hook, and the composite Action on one behavior contract.
- Preserve exit codes: `0` clean, `1` findings, `2` command/configuration/I/O error.
- `check` must never write.
- `fix` may update only one recognized stale year for the configured owner.
- Preserve the start year, Python preamble, encoding/BOM, newline style, file mode, license notice, and every non-year byte.
- Leave missing, malformed, ambiguous, future-dated, wrong-owner, and wrong-license headers unchanged.
- Refuse repairs through symlinks, reparse points, symlinked parents, hard links, or changed content.
- Keep human text, JSON schema, diagnostic codes, Action outputs, README examples, and tests synchronized.
- Do not infer ownership or license choices from Git history or neighboring files.
- Do not publish packages, tags, releases, branches, pull requests, or repository metadata unless the user explicitly requests that external action.
