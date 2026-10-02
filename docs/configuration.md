---
description: Configure explicit ownership and license policies, select languages and paths, and understand supported header layouts.
---

# Configuration

<p class="lmh-page-lead">One explicit policy for your source files. Choose the languages, paths, and notice that belong to your project.</p>

## Configuration files

Discovery searches upward from the invocation directory and selects the nearest
applicable policy. Within each directory, priority is:

| Priority | File | Policy location |
| --- | --- | --- |
| 1 | `.lmh.toml` | Top-level keys. |
| 2 | `pyproject.toml` | `[tool.lint-my-headers]`. |
| 3 | `Cargo.toml` | `[package.metadata.lint-my-headers]` or `[workspace.metadata.lint-my-headers]`. Package settings take precedence. |
| 4 | `package.json` | A `"lint-my-headers"` object. |

Manifests without LMH settings are skipped. Invalid configurations fail;
configurations are never merged. To select an exact file:

```shell
lmh check --config Cargo.toml
```

Other explicit TOML filenames use the `[tool.lint-my-headers]` section.
Configured paths are relative to the policy file. Positional CLI paths are
relative to the invocation directory. CLI policy options override file settings.

### Rust example

```toml
[package.metadata.lint-my-headers]
owner = "Example Organization"
starting-year = 2024
license = "Apache-2.0"
languages = ["rust"]
paths = ["src", "tests"]
ignore-folders = ["target"]
```

For a virtual workspace, use `[workspace.metadata.lint-my-headers]`. Go modules,
SwiftPM/Xcode projects, and shell or C/C++ projects can use `.lmh.toml`;
`go.mod`, `go.work`, and `Package.swift` do not supply header policy.

## Options

| Key / CLI option | Meaning and default |
| --- | --- |
| `owner` / `--owner` | Required exact, single-line copyright owner. |
| `starting-year` / `--starting-year` | Required earliest accepted file creation year. |
| `license` / `--license` | SPDX identifier selecting a prose notice; requires a local `LICENSE`. |
| `license-notice` / `--license-notice` | Custom notice file; configure exactly one license source. |
| `paths` / positional paths | Selected files or directories; default `.`. |
| `languages` / `--languages` | Non-empty language allowlist; default `["python"]`. |
| `ignore-files` / `--ignore-files` | Exact excluded basenames; default `["__init__.py"]`. |
| `ignore-folders` / `--ignore-folders` | Excluded subtrees; default `[".github"]`. |

Configuration lists are arrays. CLI language and ignore lists are comma-separated
and replace the corresponding configured list:

```shell
lmh check --languages typescript,rust --ignore-folders node_modules,target
```

Exclusions apply to explicit inputs too. Limit paths or exclude dependency/build
directories such as `node_modules`, `target`, `vendor`, and `.build`; excluded
subtrees are not traversed. The tool does not infer exclusions from `.gitignore`.

## Supported languages

Only enabled, supported extensions are checked, including for explicit files.
Unknown language names and empty language lists fail.

| Selector | Extensions | Header marker |
| --- | --- | --- |
| `python` | `.py` | `#` |
| `javascript` | `.js`, `.jsx`, `.mjs`, `.cjs` | `//` |
| `typescript` | `.ts`, `.tsx`, `.mts`, `.cts`, including declarations | `//` |
| `rust` | `.rs` | `//` |
| `go` | `.go`, including test and platform files | `//` |
| `swift` | `.swift`, including `Package.swift` | `//` |
| `bash` (alias `shell`) | `.sh`, `.bash` | `#` |
| `c` | `.c`, `.h` | `//` |
| `cpp` (alias `c++`) | `.cc`, `.cpp`, `.cxx`, `.c++`, `.C`, `.hh`, `.hpp`, `.hxx`, `.h++`, `.H`, `.ipp`, `.tpp`, `.inl`, `.h` | `//` |

Shared `.h` headers are checked with either C selector, using C first and falling
back to C++ when needed. Other extensions and extensionless shebang scripts are
skipped. Files are checked regardless of build tags or platform suffixes.

## Header layouts

Use the [example header](getting-started.md#check-existing-headers) with the
appropriate comment marker and blank lines. A custom `license-notice` file can
contain plain text; existing Python-commented notice files remain accepted.

??? note "Python"
    UTF-8 BOM, shebang, and PEP 263 cookie are preserved. Verified encodings:
    UTF-8, ASCII, Latin-1, and Windows-1252. Other codecs and ambiguous newer
    string syntax fail closed.

??? note "JavaScript / TypeScript"
    UTF-8 BOM, shebang, CRLF, and body are preserved. A shebang needs a blank
    separator before the header. Bare CR headers are refused.

??? note "Rust"
    UTF-8 BOM, shebang, and newline style are preserved. Use ordinary `//`
    headers; crate attributes follow the header. Shebangs need a blank separator;
    ambiguous comment-prefixed `#!` forms are refused.

??? note "Go"
    UTF-8 BOM and CRLF are preserved. Leading `//go:build` and `// +build`
    directives need a blank separator; constraints after the header are also accepted.

??? note "Swift"
    UTF-8 BOM, CRLF, and shebang are preserved. A leading
    `// swift-tools-version:` stays first, with a blank separator before the header.

??? note "Bash / shell"
    UTF-8 BOM, CRLF, shebang, and executable permissions are preserved.
    A shebang needs a blank separator; other shell dialects are skipped.

??? note "C / C++"
    UTF-8 BOM, CRLF, and body are preserved. Put include guards and
    `#pragma once` after the header. All preprocessor branches are scanned
    without evaluating them.

The non-Python parsers distinguish actual comments from strings and other
language syntax. Parse errors and copyright-bearing block/doc comments refuse
repair. Directory discovery skips symlinks and reparse points. Explicit linked
files may be checked, but repairs refuse linked files/parents, multiple hard
links, and concurrently changed targets.

The bundled SPDX snapshot is **v3.28.0**, retaining previously accepted v3.17
names/URLs, including `KiCad-libraries-exception`. Compound SPDX expressions and
new exception semantics are unsupported. Selecting a notice does not establish
legal or SPDX compliance.
