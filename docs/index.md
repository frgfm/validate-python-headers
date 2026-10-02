---
description: A Rust CLI for checking source copyright and license headers and safely refreshing recognized stale years.
---

# Lint My Headers

**Check source headers. Refresh stale years. Keep every other byte.**

Lint My Headers is a Rust command-line tool for Python, JavaScript, TypeScript,
Rust, Go, Swift, Bash/shell, C, and C++. Declare your header policy, run a read-only
check, and review any safe year updates before committing them.

```shell
lmh check   # Report findings without writing
lmh fix     # Refresh recognized stale years only
```

Both `lmh` and `lint-my-headers` expose the same commands. The installed native
CLI needs no language toolchain or Node.js runtime.

!!! info "Documentation follows main"
    The published **0.6.0** wheel supports Python with policy in `pyproject.toml`.
    Multilingual support and the additional configuration containers documented
    here require a source checkout until a release includes them. See
    [Getting started](getting-started.md) for both installation paths.

## A small, explicit workflow

1. Declare the owner, earliest creation year, license notice, and source paths.
2. Run `lmh check` locally, in CI, or from an agent task.
3. Review findings. Use `lmh fix` only for recognized, eligible stale years.

For example, a stale header produces a diagnostic with a location and repair
eligibility:

```text
src/example.py:1:1: LMH004 copyright year ends at 2025; expected 2026 [fixable]
```

The process exits **0** when clean, **1** with unresolved findings, and **2** on
an invocation, configuration, or I/O error. [JSON output](diagnostics.md#json-output)
provides the same information for automation.

## Start here

| Page | What you will find |
| --- | --- |
| [Getting started](getting-started.md) | Installation, a first policy, and a check/fix walkthrough. |
| [Configuration](configuration.md) | Discovery, options, supported languages, and header layouts. |
| [Integrations](integrations.md) | pre-commit, prek, the GitHub Action, and annual refreshes. |
| [Diagnostics & agents](diagnostics.md) | Diagnostic codes, JSON output, and agent instructions. |

## Repair boundaries

`check` never writes. `fix` preserves the creation year, body bytes, and file mode;
it changes only one recognized stale year for the configured owner. It refuses
ambiguous layouts, unsafe links, and concurrently changed targets.

Missing headers, wrong owners, malformed notices, and future years need manual
review. Lint My Headers never chooses ownership or licensing, inserts missing
headers, or establishes legal, SPDX, or REUSE compliance.

The project is licensed under
[Apache-2.0](https://github.com/frgfm/lint-my-headers/blob/main/LICENSE).
[Report an issue](https://github.com/frgfm/lint-my-headers/issues) or read the
[contributor guide](https://github.com/frgfm/lint-my-headers/blob/main/CONTRIBUTING.md).
