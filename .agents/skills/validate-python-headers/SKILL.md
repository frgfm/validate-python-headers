---
name: validate-python-headers
description: Configure, run, troubleshoot, and safely integrate validate-python-headers (vph) in Python repositories. Use whenever a user wants to check or fix Python copyright or license headers, add [tool.validate-python-headers], install its pre-commit or prek hook, configure its GitHub Action or annual review pull request, or interpret vph JSON diagnostics. Do not use to choose a license, determine copyright ownership, provide legal advice, or manage non-Python headers.
license: Apache-2.0
compatibility: Requires Python 3.11+ and vph 0.6.x for execution; setup guidance works without an installed CLI.
---

# Validate Python headers

Use `vph` as the deterministic implementation. Your job is to establish explicit policy, sequence read-only checks before authorized repairs, and explain the CLI's structured result without inventing legal facts.

## Boundaries

- Do not choose a license or determine who owns copyright. Ask the user for the exact owner, earliest accepted year, and license identifier or custom notice when the repository does not establish them unambiguously.
- Do not infer legal facts from Git history, package authors, neighboring headers, or a majority pattern.
- Do not implement a second parser or edit header text by hand.
- Do not install software, use the network, modify files, commit, push, create a branch or pull request, or change repository settings unless the user separately authorizes that action.
- Treat exit `1` as policy findings, not tool failure. Treat exit `2` as a command, configuration, path, license, or I/O failure and stop before repair.
- Use only verified released versions or immutable release SHAs in integrations. Never recommend `@main`, and never present a planned or locally installed version as already released. If network access was not authorized or no release ref exists yet, write `<RELEASE_TAG_OR_SHA>` and report that substitution as an open gate.

## Workflow

### 1. Ground in the repository

Read repository instructions, locate the repository root and nearest `pyproject.toml`, and inspect the existing working-tree state. Preserve unrelated changes.

Probe the installed contract:

```console
vph --version
vph check --help
```

The workflow in this skill requires vph 0.6.x and JSON schema version 1. If `vph` is missing or incompatible, explain the pinned installation command and stop unless installation was explicitly requested.

### 2. Establish explicit policy

Read `[tool.validate-python-headers]` from the nearest `pyproject.toml`. A runnable policy needs:

- one exact `owner`;
- one integer `starting-year`;
- exactly one `license` or `license-notice`;
- optional paths and exclusions.

If a required value is missing, conflicting, or legally ambiguous, show the evidence and ask for that decision. Do not write configuration yet unless the user asked for setup or modification.

### 3. Check before changing anything

Run the narrowest applicable read-only command:

```console
vph check --output-format json [PATH...]
```

Parse stdout as JSON. Require `schema_version == 1`; never scrape human stderr when structured output is available.

Interpret the result exactly:

- exit `0`: selected files comply;
- exit `1`: report each diagnostic path, code, message, and `fixable` flag;
- exit `2`: report `error.code`, `error.message`, and `error.path`, then stop.

Do not claim that a clean result proves license compatibility or legal compliance. It proves only that selected Python files match the configured header policy.

### 4. Repair only when explicitly requested

Before `fix`, record the pre-existing diff so unrelated changes remain distinguishable. Scope the command to the requested paths whenever possible:

```console
vph fix --output-format json [PATH...]
```

The CLI may update only recognized stale years. It deliberately leaves missing, malformed, ambiguous, future-dated, wrong-owner, wrong-license, symlinked, reparse-point, and multi-link targets unresolved.

After `fix`:

1. Read `changed` and `diagnostics` from JSON.
2. Run the same `vph check --output-format json [PATH...]` command again.
3. Inspect only the targeted diff.
4. Verify that changed files match `changed`, unresolved files match diagnostics, and unrelated pre-existing changes remain untouched.
5. Never commit or push unless the user separately asks.

### 5. Configure integrations only when requested

- Put policy in `pyproject.toml`; do not duplicate it in each integration.
- Prefer the first-party `vph` pre-commit hook and a verified released tag or immutable SHA. Use an explicit placeholder when the release cannot be verified without unauthorized network access.
- Give pull-request checks read-only `contents` permission.
- Treat annual year refresh as an optional project convention. Use a deterministic review branch and pull request, never a direct default-branch write.
- Preserve existing Action inputs for compatibility, but omit overrides when repository config is authoritative.

## Report format

Return a concise operational report:

```markdown
## Header policy
- Config: <path or missing>
- Owner / starting year / license source: <explicit values or unresolved decision>

## Check result
- Checked: <count>
- Status: clean | findings | command error
- Findings: <path, code, message, fixable>

## Changes
- Changed: <paths or none>
- Unresolved: <paths and reasons or none>
- Validation: <recheck result and targeted diff status>

## Remaining gate
- <only a real unresolved decision, external action, or unrun check>
```

Omit the Changes section for a read-only request. Clearly separate local evidence from unrun CI, published-package, remote-Action, or live-provider checks.
