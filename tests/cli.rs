use chrono::{Datelike, Local};
use serde_json::{Value, json};
use std::{
    fs,
    path::Path,
    process::{Command, Stdio},
};
use tempfile::{TempDir, tempdir};

const OWNER: &str = "Example Owner";
const NOTICE: &str = "# This program is licensed under the Apache License 2.0.\n# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.\n";
const CONFIG: &str = "[tool.lint-my-headers]\nowner = 'Example Owner'\nstarting-year = 2022\nlicense = 'Apache-2.0'\npaths = ['src']\nignore-files = []\nignore-folders = []\n";

fn workspace() -> TempDir {
    let dir = tempdir().unwrap();
    let root = dir.path();
    fs::write(root.join("LICENSE"), "Apache-2.0\n").unwrap();
    fs::write(root.join("pyproject.toml"), CONFIG).unwrap();
    fs::create_dir(root.join("src")).unwrap();
    dir
}

fn year() -> i32 {
    Local::now().year()
}

fn source(years: impl std::fmt::Display, owner: &str, notice: &str) -> String {
    format!("# Copyright (C) {years}, {owner}.\n\n{notice}\nvalue = 'café'\n")
}

fn header(years: impl std::fmt::Display) -> String {
    source(years, OWNER, NOTICE)
}

fn message(result: &Value) -> &str {
    result["error"]["message"].as_str().unwrap()
}

fn write(root: &Path, name: &str, contents: impl AsRef<[u8]>) {
    let path = root.join(name);
    fs::create_dir_all(path.parent().unwrap()).unwrap();
    fs::write(path, contents).unwrap();
}

fn run(root: &Path, args: &[&str], exit: i32) -> std::process::Output {
    let output = Command::new(env!("CARGO_BIN_EXE_lmh"))
        .current_dir(root)
        .env("PATH", "")
        .env_remove("GITHUB_OUTPUT")
        .args(args)
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(exit), "{args:?}: {output:?}");
    output
}

fn json_run(root: &Path, args: &[&str], exit: i32) -> Value {
    let mut args = args.to_vec();
    args.extend(["--output-format", "json"]);
    let output = run(root, &args, exit);
    assert!(output.stderr.is_empty(), "{output:?}");
    serde_json::from_slice(&output.stdout).unwrap()
}

#[test]
fn go_files_use_standalone_policy_and_include_tests_and_platform_variants() {
    let dir = workspace();
    let root = dir.path();
    fs::remove_file(root.join("pyproject.toml")).unwrap();
    write(root, "go.mod", "module example.com/project\n\ngo 1.22\n");
    let config = CONFIG.strip_prefix("[tool.lint-my-headers]\n").unwrap();
    write(root, ".lmh.toml", format!("{config}languages = ['go']\n"));
    let original = header(year() - 2)
        .replace("# ", "// ")
        .replace("value = 'café'", "package example\nconst value = \"café\"");
    for name in ["main.go", "main_test.go", "main_windows.go"] {
        write(root, &format!("src/{name}"), &original);
    }
    write(root, "src/example.py", header(year()));
    let checked = json_run(root, &["check"], 1);
    assert_eq!(checked["config_path"], ".lmh.toml");
    assert_eq!(checked["checked"], 3);
    assert_eq!(
        fs::read_to_string(root.join("src/main.go")).unwrap(),
        original
    );
    let fixed = json_run(root, &["fix"], 0);
    assert_eq!(fixed["changed"].as_array().unwrap().len(), 3);
    assert_eq!(
        fs::read_to_string(root.join("src/main.go")).unwrap(),
        original.replacen(
            &(year() - 2).to_string(),
            &format!("{}-{}", year() - 2, year()),
            1
        )
    );
    assert_eq!(json_run(root, &["fix"], 0)["changed"], json!([]));
    assert_eq!(
        json_run(root, &["check", "--languages", "python", "src/main.go"], 0)["checked"],
        0
    );
    assert_eq!(
        json_run(
            root,
            &["check", "--ignore-files", "main.go", "src/main.go"],
            0
        )["checked"],
        0
    );
}

#[test]
fn rust_check_and_fix_use_cargo_package_or_workspace_policy() {
    let dir = workspace();
    let root = dir.path();
    fs::remove_file(root.join("pyproject.toml")).unwrap();
    let original = header(year() - 2)
        .replace("# ", "// ")
        .replace("value = 'café'", "const VALUE: &str = \"café\";");
    write(root, "src/example.py", header(year()));
    let table = CONFIG.strip_prefix("[tool.lint-my-headers]\n").unwrap();
    for section in ["package.metadata", "workspace.metadata"] {
        let manifest = if section == "package.metadata" {
            "[package]\nname = 'example'\nversion = '0.1.0'\nedition = '2024'\n"
        } else {
            "[workspace]\nmembers = []\n"
        };
        write(
            root,
            "Cargo.toml",
            format!("{manifest}[{section}.lint-my-headers]\n{table}languages = ['rust']\n"),
        );
        write(root, "src/lib.rs", &original);
        let checked = json_run(root, &["check"], 1);
        assert_eq!(checked["config_path"], "Cargo.toml");
        assert_eq!(checked["checked"], 1);
        assert_eq!(checked["diagnostics"][0]["code"], "LMH004");
        assert!(
            checked["expected_header"]
                .as_str()
                .unwrap()
                .starts_with("// Copyright")
        );
        assert_eq!(
            fs::read_to_string(root.join("src/lib.rs")).unwrap(),
            original
        );
        assert_eq!(
            json_run(root, &["fix"], 0)["changed"],
            json!(["src/lib.rs"])
        );
        assert_eq!(
            fs::read_to_string(root.join("src/lib.rs")).unwrap(),
            original.replacen(
                &(year() - 2).to_string(),
                &format!("{}-{}", year() - 2, year()),
                1
            )
        );
        assert_eq!(json_run(root, &["fix"], 0)["changed"], json!([]));
        assert_eq!(
            json_run(root, &["check", "--languages", "python", "src/lib.rs"], 0)["checked"],
            0
        );
    }
    write(
        root,
        ".lmh.toml",
        format!("{table}languages = ['python']\n"),
    );
    assert_eq!(json_run(root, &["check"], 0)["config_path"], ".lmh.toml");
    assert_eq!(
        json_run(root, &["check", "--config", "Cargo.toml"], 0)["checked"],
        1
    );
}

#[test]
fn language_selection_and_shared_notices_work_for_every_extension() {
    let dir = workspace();
    let root = dir.path();
    write(root, "notice.txt", "Proprietary.\n\nAll rights reserved.\n");
    let extensions = [
        "js", "jsx", "mjs", "cjs", "ts", "tsx", "mts", "cts", "d.ts", "d.mts", "d.cts",
    ];
    let original = source(
        year() - 2,
        OWNER,
        "# Proprietary.\n\n# All rights reserved.\n",
    );
    write(root, "src/example.py", &original);
    for extension in extensions {
        write(
            root,
            &format!("src/example.{extension}"),
            original.replace("# ", "// "),
        );
    }
    write(root, "src/unsupported.rs", "unrecognized source\n");
    assert_eq!(
        json_run(root, &["check", "--license-notice", "notice.txt"], 1)["checked"],
        1
    );
    let args = [
        "--languages",
        "python,javascript,typescript",
        "--license-notice",
        "notice.txt",
    ];
    let checked = json_run(root, &[&["check"], &args[..]].concat(), 1);
    assert_eq!(checked["checked"], extensions.len() + 1);
    assert_eq!(
        fs::read_to_string(root.join("src/example.ts")).unwrap(),
        original.replace("# ", "// ")
    );
    let fixed = json_run(root, &[&["fix"], &args[..]].concat(), 0);
    assert_eq!(
        fixed["changed"].as_array().unwrap().len(),
        extensions.len() + 1
    );
    for extension in extensions {
        assert_eq!(
            fs::read_to_string(root.join(format!("src/example.{extension}"))).unwrap(),
            original.replace("# ", "// ").replacen(
                &(year() - 2).to_string(),
                &format!("{}-{}", year() - 2, year()),
                1
            )
        );
    }
    assert_eq!(
        json_run(root, &[&["fix"], &args[..]].concat(), 0)["changed"],
        json!([])
    );
    assert_eq!(
        json_run(root, &["check", "src/example.ts", "src/unsupported.rs"], 0)["checked"],
        0
    );
    let selected = json_run(
        root,
        &[
            "check",
            "--languages",
            "typescript",
            "--license-notice",
            "notice.txt",
            "src/example.ts",
        ],
        0,
    );
    assert!(
        selected["expected_header"]
            .as_str()
            .unwrap()
            .starts_with("// Copyright")
    );
    assert_eq!(
        json_run(
            root,
            &[
                "check",
                "--languages",
                "typescript",
                "--license-notice",
                "notice.txt",
                "--ignore-files",
                "example.ts",
                "src/example.ts"
            ],
            0
        )["checked"],
        0
    );
}

#[test]
fn project_configuration_fallbacks_precedence_and_explicit_selection() {
    let dir = workspace();
    let root = dir.path();
    write(root, "src/example.ts", header(year()).replace("# ", "// "));
    let table = CONFIG.strip_prefix("[tool.lint-my-headers]\n").unwrap();
    let configs = [
        (".lmh.toml", format!("{table}languages = ['typescript']\n")),
        (
            "pyproject.toml",
            format!("{CONFIG}languages = ['typescript']\n"),
        ),
        (
            "Cargo.toml",
            format!("[workspace.metadata.lint-my-headers]\n{table}languages = ['typescript']\n"),
        ),
        (
            "package.json",
            json!({"name": "example", "lint-my-headers": {
                "owner": OWNER, "starting-year": 2022, "license": "Apache-2.0",
                "paths": ["src"], "languages": ["typescript"]
            }})
            .to_string(),
        ),
    ];
    for (name, contents) in &configs {
        write(root, name, contents);
    }
    fs::create_dir(root.join("nested")).unwrap();
    assert_eq!(
        json_run(root, &["check", "--config", "package.json"], 0)["config_path"],
        "package.json"
    );
    for (name, _) in &configs {
        let result = json_run(&root.join("nested"), &["check"], 0);
        assert_eq!(result["config_path"], *name);
        assert_eq!(result["checked"], 1);
        fs::remove_file(root.join(name)).unwrap();
    }
    write(
        root,
        "Cargo.toml",
        configs[2]
            .1
            .replace("workspace.metadata", "package.metadata"),
    );
    write(root, "pyproject.toml", "[project]\nname = 'unrelated'\n");
    assert_eq!(json_run(root, &["check"], 0)["config_path"], "Cargo.toml");
    write(root, ".lmh.toml", &configs[0].1);
    write(root, "nested/LICENSE", "Apache-2.0\n");
    write(
        root,
        "nested/package.json",
        configs[3].1.replace("\"src\"", "\"../src\""),
    );
    assert_eq!(
        json_run(&root.join("nested"), &["check"], 0)["config_path"],
        "package.json"
    );
    write(root, "nested/.lmh.toml", "languages = []\n");
    assert_eq!(
        json_run(&root.join("nested"), &["fix"], 2)["changed"],
        json!([])
    );
    for invalid in [
        "lint-my-headers = null",
        "{\"lint-my-headers\": []}",
        "{\"lint-my-headers\": {\"languages\": [\"typo\"]}}",
    ] {
        write(root, "package.json", invalid);
        assert_eq!(
            json_run(root, &["fix", "--config", "package.json"], 2)["changed"],
            json!([])
        );
    }
    write(root, "custom.toml", "[tool.ruff]\nline-length = 100\n");
    let result = json_run(
        root,
        &[
            "check",
            "--config",
            "custom.toml",
            "--owner",
            OWNER,
            "--starting-year",
            "2022",
            "--license",
            "Apache-2.0",
            "--languages",
            "typescript",
            "src/example.ts",
        ],
        0,
    );
    assert_eq!(result["checked"], 1);
    write(root, "custom.toml", &configs[1].1);
    assert_eq!(
        json_run(root, &["check", "--config", "custom.toml"], 0)["checked"],
        1
    );
}

#[test]
fn native_commands_help_version_and_legacy_names() {
    let dir = workspace();
    let root = dir.path();
    let version = run(root, &["--version"], 0);
    assert!(
        String::from_utf8(version.stdout)
            .unwrap()
            .ends_with(&format!(
                " {}\n",
                env!("CARGO_PKG_VERSION").replace("-rc.", "rc")
            ))
    );
    for binary in [
        env!("CARGO_BIN_EXE_lmh"),
        env!("CARGO_BIN_EXE_lint-my-headers"),
    ] {
        let output = Command::new(binary)
            .env("PATH", "")
            .arg("--help")
            .output()
            .unwrap();
        assert!(output.status.success(), "{output:?}");
        let help = String::from_utf8(output.stdout).unwrap();
        assert!(help.contains("check") && help.contains("fix"));
    }
    for removed in ["vph", "validate-python-headers", "validate_headers"] {
        run(root, &[removed], 2);
    }
    write(
        root,
        "pyproject.toml",
        CONFIG.replace("lint-my-headers", "validate-python-headers"),
    );
    let result = json_run(root, &["check"], 2);
    assert!(message(&result).contains("owner"));
}

#[test]
fn check_json_is_ordered_complete_and_read_only() {
    let dir = workspace();
    let root = dir.path();
    write(root, "src/b.py", "value = 1\n");
    let stale = header(year() - 2);
    write(root, "src/a.py", &stale);
    let before = fs::metadata(root.join("src/a.py"))
        .unwrap()
        .modified()
        .unwrap();
    let output = run(root, &["check", "--output-format", "json"], 1);
    assert!(output.stderr.is_empty());
    let text = String::from_utf8(output.stdout).unwrap();
    let keys = [
        "schema_version",
        "tool_version",
        "command",
        "config_path",
        "checked",
        "changed",
        "diagnostics",
        "expected_header",
        "error",
    ];
    let positions: Vec<_> = keys
        .iter()
        .map(|key| text.find(&format!("\"{key}\":")).unwrap())
        .collect();
    assert!(positions.windows(2).all(|pair| pair[0] < pair[1]));
    let result: Value = serde_json::from_str(&text).unwrap();
    assert_eq!(result["schema_version"], 1);
    assert_eq!(result["command"], "check");
    assert_eq!(result["config_path"], "pyproject.toml");
    assert_eq!(result["checked"], 2);
    assert_eq!(result["changed"], json!([]));
    assert_eq!(result["diagnostics"][0]["path"], "src/a.py");
    assert_eq!(result["diagnostics"][0]["code"], "LMH004");
    assert_eq!(result["diagnostics"][0]["fixable"], true);
    assert_eq!(result["diagnostics"][1]["path"], "src/b.py");
    assert_eq!(result["diagnostics"][1]["code"], "LMH001");
    assert!(result["error"].is_null());
    assert!(
        result["expected_header"]
            .as_str()
            .unwrap()
            .contains("<FILE_CREATION_YEAR>")
    );
    assert_eq!(fs::read(root.join("src/a.py")).unwrap(), stale.as_bytes());
    assert_eq!(
        fs::metadata(root.join("src/a.py"))
            .unwrap()
            .modified()
            .unwrap(),
        before
    );
}

#[test]
fn concurrent_hook_processes_append_complete_action_output_records() {
    let dir = workspace();
    let root = dir.path();
    write(root, "src/clean.py", header(year()));
    let output_path = root.join("github-output.txt");
    let children: Vec<_> = (0..32)
        .map(|_| {
            Command::new(env!("CARGO_BIN_EXE_lmh"))
                .current_dir(root)
                .env("PATH", "")
                .env("GITHUB_OUTPUT", &output_path)
                .args(["check", "--output-format", "json"])
                .stdout(Stdio::null())
                .stderr(Stdio::piped())
                .spawn()
                .unwrap()
        })
        .collect();
    for child in children {
        let result = child.wait_with_output().unwrap();
        assert!(result.status.success(), "{result:?}");
    }
    assert_eq!(
        fs::read_to_string(output_path).unwrap(),
        "issues=[]\nchanged=[]\n".repeat(32)
    );
}

#[test]
fn text_diagnostics_and_action_outputs_remain_compatible() {
    let dir = workspace();
    let root = dir.path();
    write(root, "src/stale.py", header(year() - 2));
    write(root, "src/missing.py", "value = 1\n");
    let output = run(root, &["check"], 1);
    assert!(output.stdout.is_empty());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("src/stale.py:1:1: LMH004"));
    assert!(stderr.contains("[fixable]") && stderr.contains("Expected header:"));
    let action_output = root.join("github-output.txt");
    let output = Command::new(env!("CARGO_BIN_EXE_lmh"))
        .current_dir(root)
        .env("PATH", "")
        .env("GITHUB_OUTPUT", &action_output)
        .arg("fix")
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(1), "{output:?}");
    assert_eq!(
        fs::read_to_string(&action_output).unwrap(),
        "issues=[\"src/missing.py\"]\nchanged=[\"src/stale.py\"]\n"
    );
    assert!(
        String::from_utf8(output.stdout)
            .unwrap()
            .contains("Updated headers:\n- src/stale.py\n")
    );
    let output = Command::new(env!("CARGO_BIN_EXE_lmh"))
        .current_dir(root)
        .env("GITHUB_OUTPUT", &action_output)
        .args(["check", "--output-format", "json", "missing.py"])
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(2));
    assert!(output.stderr.is_empty());
    let result: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(result["checked"], 0);
    assert_eq!(result["diagnostics"], json!([]));
    assert_eq!(result["error"]["code"], "LMH900");
    assert!(!result["expected_header"].is_null());
    assert!(
        fs::read_to_string(action_output)
            .unwrap()
            .ends_with("issues=[]\nchanged=[]\n")
    );
}

#[test]
fn diagnostic_precedence_and_unfixable_sources() {
    let dir = workspace();
    let root = dir.path();
    let invalid = [
        ("missing", "value = 1\n".to_owned(), "LMH001"),
        (
            "owner",
            source(year() + 1, "Another Owner", "# Wrong.\n"),
            "LMH002",
        ),
        ("future", source(year() + 1, OWNER, "# Wrong.\n"), "LMH003"),
        (
            "reversed",
            source(format!("{}-{}", year() - 1, year() - 2), OWNER, NOTICE),
            "LMH003",
        ),
        ("old", source("2021", OWNER, NOTICE), "LMH003"),
        ("license", source(year() - 2, OWNER, "# Wrong.\n"), "LMH005"),
        ("layout", source("20x4", "Another Owner", NOTICE), "LMH006"),
        (
            "duplicate",
            format!(
                "{}# Copyright (C) {}, {OWNER}.\n",
                header(year() - 2),
                year()
            ),
            "LMH006",
        ),
        (
            "decode",
            "# coding: made-up-codec\nvalue = 1\n".to_owned(),
            "LMH007",
        ),
        (
            "late_cookie",
            format!("value = 0\n# coding: utf-8\n\n{}", header(year())),
            "LMH006",
        ),
    ];
    for (name, contents, _) in &invalid {
        write(root, &format!("src/{name}.py"), contents);
    }
    write(root, "src/stale.py", header(year() - 2));
    let result = json_run(root, &["fix"], 1);
    assert_eq!(result["changed"], json!(["src/stale.py"]));
    let diagnostics = result["diagnostics"].as_array().unwrap();
    assert_eq!(diagnostics.len(), invalid.len());
    for (name, contents, code) in invalid {
        let path = format!("src/{name}.py");
        let diagnostic = diagnostics.iter().find(|d| d["path"] == path).unwrap();
        assert_eq!(diagnostic["code"], code, "{name}");
        assert_eq!(diagnostic["fixable"], false, "{name}");
        assert_eq!(fs::read_to_string(root.join(path)).unwrap(), contents);
    }
}

#[test]
fn python_preambles_and_string_examples_are_accepted() {
    let dir = workspace();
    let root = dir.path();
    for (name, preamble) in [
        ("single", ""),
        ("shebang", "#!/usr/bin/env python3\n\n"),
        ("cookie", "# coding: utf-8\n\n"),
        (
            "both",
            "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n\n",
        ),
        ("second_cookie", "# A comment\n# coding=utf-8\n\n"),
    ] {
        write(
            root,
            &format!("src/{name}.py"),
            format!("{preamble}{}", header(year())),
        );
    }
    write(root, "src/range.py", header(format!("2024-{}", year())));
    write(
        root,
        "src/example.py",
        format!(
            "{}EXAMPLE = '''\n# Copyright (C) 2024, Someone Else.\n'''\n",
            header(year())
        ),
    );
    let result = json_run(root, &["check"], 0);
    assert_eq!(result["checked"], 7);
    assert_eq!(result["diagnostics"], json!([]));
}

#[test]
fn fix_preserves_bytes_mode_and_is_idempotent() {
    let dir = workspace();
    let root = dir.path();
    write(
        root,
        "notice.txt",
        "# Proprietary.\n# All rights reserved.\n",
    );
    let notice = "# Proprietary.\n# All rights reserved.\n";
    let original = format!(
        "\u{feff}#!/usr/bin/env python3\n# coding: utf-8\n\n{}",
        source(year() - 2, OWNER, notice)
    )
    .replace('\n', "\r\n");
    let expected = original.replacen(
        &format!("Copyright (C) {},", year() - 2),
        &format!("Copyright (C) {}-{},", year() - 2, year()),
        1,
    );
    write(root, "src/stale.py", &original);
    let path = root.join("src/stale.py");
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&path, fs::Permissions::from_mode(0o754)).unwrap();
    }
    let result = json_run(root, &["fix", "--license-notice", "notice.txt"], 0);
    assert_eq!(result["changed"], json!(["src/stale.py"]));
    assert_eq!(fs::read(&path).unwrap(), expected.as_bytes());
    let modified = fs::metadata(&path).unwrap().modified().unwrap();
    let result = json_run(root, &["fix", "--license-notice", "notice.txt"], 0);
    assert_eq!(result["changed"], json!([]));
    assert_eq!(fs::read(&path).unwrap(), expected.as_bytes());
    assert_eq!(fs::metadata(&path).unwrap().modified().unwrap(), modified);
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        assert_eq!(
            fs::metadata(path).unwrap().permissions().mode() & 0o777,
            0o754
        );
    }
}

#[test]
fn non_utf8_sources_keep_their_original_encoding() {
    let dir = workspace();
    let root = dir.path();
    let raw = format!(
        "# coding: latin-1\n\n{}",
        source(year() - 2, "André", NOTICE)
    );
    let bytes: Vec<u8> = raw.chars().map(|ch| ch as u8).collect();
    write(root, "src/latin.py", &bytes);
    let result = json_run(root, &["fix", "--owner", "André"], 0);
    assert_eq!(result["changed"], json!(["src/latin.py"]));
    let expected: Vec<u8> = raw
        .replacen(
            &format!("Copyright (C) {},", year() - 2),
            &format!("Copyright (C) {}-{},", year() - 2, year()),
            1,
        )
        .chars()
        .map(|ch| ch as u8)
        .collect();
    assert_eq!(fs::read(root.join("src/latin.py")).unwrap(), expected);
}

#[test]
fn nearest_configuration_cli_precedence_and_root_relative_paths() {
    let dir = workspace();
    let root = dir.path();
    write(root, "src/clean.py", header(year()));
    fs::create_dir_all(root.join("nested/deep")).unwrap();
    let nested = root.join("nested/deep");
    let configured = json_run(&nested, &["check"], 0);
    assert_eq!(configured["checked"], 1);
    assert_eq!(configured["config_path"], "pyproject.toml");
    write(root, "notice.txt", "# Proprietary.\n");
    write(
        root,
        "nested/deep/selected.py",
        source(year() - 2, "CLI Owner", "# Proprietary.\n"),
    );
    let result = json_run(
        &nested,
        &[
            "check",
            "--owner",
            "CLI Owner",
            "--starting-year",
            "2024",
            "--license-notice",
            "../../notice.txt",
            "selected.py",
        ],
        1,
    );
    assert_eq!(result["checked"], 1);
    assert_eq!(result["diagnostics"][0]["path"], "nested/deep/selected.py");
    assert_eq!(result["diagnostics"][0]["code"], "LMH004");
    write(
        root,
        "nested/pyproject.toml",
        CONFIG
            .replace("Example Owner", "Nested Owner")
            .replace("paths = ['src']", "paths = ['deep']"),
    );
    write(root, "nested/LICENSE", "Apache-2.0\n");
    let result = json_run(&nested, &["check"], 1);
    assert_eq!(result["diagnostics"][0]["path"], "deep/selected.py");
    assert_eq!(result["diagnostics"][0]["code"], "LMH002");
    let result = json_run(&nested, &["check", "--config", "../../pyproject.toml"], 0);
    assert_eq!(result["checked"], 1);
}

#[test]
fn configured_custom_notice_is_relative_to_the_config() {
    let dir = workspace();
    let root = dir.path();
    write(root, "notice.txt", "# Proprietary.\r\n");
    write(
        root,
        "pyproject.toml",
        CONFIG.replace("license = 'Apache-2.0'", "license-notice = 'notice.txt'"),
    );
    write(
        root,
        "src/clean.py",
        source(year(), OWNER, "# Proprietary.\n"),
    );
    fs::create_dir(root.join("nested")).unwrap();
    fs::remove_file(root.join("LICENSE")).unwrap();
    assert_eq!(json_run(&root.join("nested"), &["check"], 0)["checked"], 1);
}

#[test]
fn invalid_config_is_rejected_before_any_write() {
    let dir = workspace();
    let root = dir.path();
    let stale = header(year() - 2);
    write(root, "src/stale.py", &stale);
    for (key, value) in [
        ("owner", "true"),
        ("owner", "''"),
        ("starting-year", "true"),
        ("starting-year", "2022.0"),
        ("starting-year", "999"),
        ("license", "4"),
        ("license-notice", "false"),
        ("paths", "[]"),
        ("paths", "['']"),
        ("paths", "'src'"),
        ("languages", "[]"),
        ("languages", "['typo']"),
        ("languages", "'typescript'"),
        ("ignore-files", "[42]"),
        ("ignore-folders", "true"),
        ("unknown-key", "true"),
    ] {
        let filtered: Vec<_> = CONFIG
            .lines()
            .filter(|line| !line.starts_with(&format!("{key} =")))
            .collect();
        write(
            root,
            "pyproject.toml",
            format!("{}\n{key} = {value}\n", filtered.join("\n")),
        );
        let result = json_run(root, &["fix"], 2);
        assert_eq!(result["error"]["code"], "LMH900", "{key}={value}");
        assert!(
            message(&result).contains(&format!("[tool.lint-my-headers].{key}")),
            "{result}"
        );
        assert_eq!(result["changed"], json!([]));
        assert_eq!(
            fs::read_to_string(root.join("src/stale.py")).unwrap(),
            stale
        );
    }
    write(
        root,
        "pyproject.toml",
        format!("{CONFIG}license-notice = 'notice.txt'\n"),
    );
    assert!(
        json_run(root, &["fix"], 2)["error"]["message"]
            .as_str()
            .unwrap()
            .contains("exactly one")
    );
    write(root, "pyproject.toml", CONFIG);
    for args in [
        vec!["fix", "--folders", "src", "src/stale.py"],
        vec!["fix", "--license", "made-up-license"],
        vec!["fix", "--config", "missing.toml"],
        vec!["fix", "--owner", "bad\nowner"],
    ] {
        assert_eq!(json_run(root, &args, 2)["changed"], json!([]));
    }
    let missing = json_run(root, &["check", "--config", "missing.toml"], 2);
    json_run(
        root,
        &["fix", "--starting-year", &(year() + 1).to_string()],
        2,
    );
    json_run(root, &["fix", "--license", ""], 2);
    assert_eq!(missing["config_path"], "missing.toml");
    assert_eq!(missing["error"]["path"], "missing.toml");
    assert_eq!(
        fs::read_to_string(root.join("src/stale.py")).unwrap(),
        stale
    );
}

#[test]
fn discovery_deduplicates_ignores_and_sorts_external_paths() {
    let outer = tempdir().unwrap();
    let root = outer.path().join("project");
    fs::create_dir(&root).unwrap();
    write(&root, "LICENSE", "Apache-2.0\n");
    write(&root, "pyproject.toml", CONFIG);
    for file in ["src/a.py", "src/z.py", "src/ignored.py", "src/skip/bad.py"] {
        write(&root, file, "value = 1\n");
    }
    write(outer.path(), "external.py", "value = 1\n");
    let result = json_run(
        &root,
        &[
            "check",
            "--ignore-files",
            "ignored.py",
            "--ignore-folders",
            "src/skip",
            "src",
            "src/a.py",
            "../external.py",
        ],
        1,
    );
    assert_eq!(result["checked"], 3);
    let paths: Vec<_> = result["diagnostics"]
        .as_array()
        .unwrap()
        .iter()
        .map(|d| d["path"].as_str().unwrap())
        .collect();
    assert_eq!(paths, ["../external.py", "src/a.py", "src/z.py"]);
}

#[cfg(windows)]
#[test]
fn display_paths_match_verbatim_and_regular_prefixes() {
    for (root, path, expected) in [
        (r"\\?\C:\repo", r"C:\repo\src\a.py", "src/a.py"),
        (r"C:\repo", r"\\?\C:\external.py", "../external.py"),
        (
            r"\\?\UNC\server\share\repo",
            r"\\server\share\repo\src\a.py",
            "src/a.py",
        ),
    ] {
        assert_eq!(
            lint_my_headers::display_path(Path::new(path), Path::new(root)),
            expected
        );
    }
}

#[test]
fn hardlinked_targets_are_readable_but_never_fixed() {
    let dir = workspace();
    let root = dir.path();
    let stale = header(year() - 2);
    write(root, "src/first.py", &stale);
    fs::hard_link(root.join("src/first.py"), root.join("src/second.py")).unwrap();
    let check = json_run(root, &["check", "src/first.py"], 1);
    assert_eq!(check["diagnostics"][0]["code"], "LMH004");
    assert_eq!(check["diagnostics"][0]["fixable"], false);
    let fixed = json_run(root, &["fix"], 1);
    assert_eq!(fixed["changed"], json!([]));
    for diagnostic in fixed["diagnostics"].as_array().unwrap() {
        assert_eq!(diagnostic["code"], "LMH008");
    }
    for path in ["src/first.py", "src/second.py"] {
        assert_eq!(fs::read_to_string(root.join(path)).unwrap(), stale);
    }
}

#[cfg(any(unix, windows))]
#[test]
fn symlinks_are_skipped_during_discovery_and_refused_during_fix() {
    let dir = workspace();
    let root = dir.path();
    let stale = header(year() - 2);
    write(root, "outside/target.py", &stale);
    let target = root.join("outside/target.py");
    let link = root.join("src/link.py");
    #[cfg(unix)]
    std::os::unix::fs::symlink(&target, &link).unwrap();
    #[cfg(windows)]
    if let Err(error) = std::os::windows::fs::symlink_file(&target, &link) {
        if error.raw_os_error() == Some(1314) {
            return;
        }
        panic!("{error}");
    }
    assert_eq!(json_run(root, &["check"], 0)["checked"], 0);
    let check = json_run(root, &["check", "src/link.py"], 1);
    assert_eq!(check["diagnostics"][0]["code"], "LMH004");
    assert_eq!(check["diagnostics"][0]["fixable"], false);
    let fixed = json_run(root, &["fix", "src/link.py"], 1);
    assert_eq!(fixed["diagnostics"][0]["code"], "LMH008");
    assert_eq!(fs::read_to_string(&target).unwrap(), stale);
    assert!(
        fs::symlink_metadata(&link)
            .unwrap()
            .file_type()
            .is_symlink()
    );
    let linked_root = root.join("linked-root");
    #[cfg(unix)]
    std::os::unix::fs::symlink(root.join("outside"), &linked_root).unwrap();
    #[cfg(windows)]
    std::os::windows::fs::symlink_dir(root.join("outside"), &linked_root).unwrap();
    assert_eq!(json_run(root, &["check", "linked-root"], 2)["checked"], 0);
    let result = json_run(root, &["fix", "linked-root/target.py"], 1);
    assert_eq!(result["diagnostics"][0]["code"], "LMH008");
    assert_eq!(fs::read_to_string(target).unwrap(), stale);
}

#[test]
fn pinned_spdx_data_accepts_every_legacy_notice_and_new_identifiers() {
    use sha2::{Digest, Sha256};
    let snapshot = include_bytes!("../src/lint_my_headers/supported-licenses.json");
    assert_eq!(
        format!("{:x}", Sha256::digest(snapshot)),
        "f728c534d8bd1044fc515a2ddb2292be99559021d830bfa3281be0bcd36302ee"
    );
    let current: Value = serde_json::from_slice(snapshot).unwrap();
    assert_eq!(current["licenseListVersion"], "3.28.0");
    assert_eq!(current["licenses"].as_array().unwrap().len(), 727);
    let legacy: Value = serde_json::from_str(include_str!(
        "../src/lint_my_headers/legacy-license-notices.json"
    ))
    .unwrap();
    assert_eq!(legacy["baseline_version"], "3.17");
    let licenses = legacy["licenses"].as_object().unwrap();
    assert_eq!(licenses.len(), 29);
    let dir = workspace();
    let root = dir.path();
    for (identifier, entry) in licenses {
        for url in entry["urls"].as_array().unwrap() {
            let notice = format!(
                "# This program is licensed under the {}.\n# See LICENSE or go to <{}> for full license details.\n",
                entry["name"].as_str().unwrap(),
                url.as_str().unwrap()
            );
            write(root, "src/valid.py", source(year(), OWNER, &notice));
            let result = json_run(root, &["check", "--license", identifier], 0);
            assert_eq!(result["checked"], 1, "{identifier}");
        }
    }
    let new = current["licenses"]
        .as_array()
        .unwrap()
        .iter()
        .find(|item| item["licenseId"] == "3D-Slicer-1.0")
        .unwrap();
    let notice = format!(
        "# This program is licensed under the {}.\n# See LICENSE or go to <{}> for full license details.\n",
        new["name"].as_str().unwrap(),
        new["seeAlso"][0].as_str().unwrap()
    );
    write(root, "src/valid.py", source(year(), OWNER, &notice));
    let result = json_run(
        root,
        &[
            "check",
            "--license",
            "3D-Slicer-1.0",
            "--starting-year",
            &year().to_string(),
        ],
        0,
    );
    assert_eq!(result["checked"], 1);
    assert!(
        result["expected_header"]
            .as_str()
            .unwrap()
            .starts_with(&format!("# Copyright (C) {}, {OWNER}.", year()))
    );
}
