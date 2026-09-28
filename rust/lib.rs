pub mod analysis;
pub mod config;
pub mod filesystem;
pub mod model;

use chrono::Datelike;
use clap::{CommandFactory, FromArgMatches};
use config::{Cli, OutputFormat};
use filesystem::RepairError;
use model::{CommandResult, Diagnostic, Settings};
use std::io::{self, Write};
use std::path::{Component, Path, PathBuf};

pub fn version() -> String {
    env!("CARGO_PKG_VERSION").replace("-rc.", "rc")
}

pub fn display_path(path: &Path, root: &Path) -> String {
    fn absolute(path: &Path) -> PathBuf {
        let path = if path.is_absolute() {
            path.to_path_buf()
        } else {
            std::env::current_dir().unwrap_or_default().join(path)
        };
        let mut normal = PathBuf::new();
        for part in path.components() {
            match part {
                Component::CurDir => {}
                Component::ParentDir => {
                    normal.pop();
                }
                _ => normal.push(part.as_os_str()),
            }
        }
        normal
    }
    let path = absolute(path);
    pathdiff::diff_paths(&path, absolute(root))
        .unwrap_or(path)
        .to_string_lossy()
        .replace('\\', "/")
}

pub fn run(settings: &Settings, command: &str, current_year: i32) -> CommandResult {
    let mut result = CommandResult::new(command);
    result.config_path = settings
        .config_path
        .as_ref()
        .map(|p| display_path(p, &settings.project_root));
    let policy = match analysis::build_policy(settings, current_year) {
        Ok(policy) => policy,
        Err(error) => {
            result.fail(error, None);
            return result;
        }
    };
    result.expected_header = Some(policy.expected_header.clone());
    let mut paths = match filesystem::discover(settings) {
        Ok(paths) => paths,
        Err(error) => {
            result.fail(error, None);
            return result;
        }
    };
    paths.sort_by_key(|p| display_path(p, &settings.project_root));
    let mut files = Vec::with_capacity(paths.len());
    for path in &paths {
        let shown = display_path(path, &settings.project_root);
        let snapshot = match filesystem::read(path, &settings.project_root) {
            Ok(snapshot) => snapshot,
            Err(error) => {
                result.fail(error, Some(shown));
                return result;
            }
        };
        let mut content = analysis::analyze(&snapshot.bytes, &policy, &shown);
        if let Some(diagnostic) = &mut content.diagnostic {
            if diagnostic.code == "LMH004" {
                diagnostic.fixable =
                    snapshot.unsafe_reason.is_none() && content.replacement.is_some();
            }
            result.diagnostics.push(diagnostic.clone());
        }
        result.checked += 1;
        files.push((snapshot, content));
    }
    if command == "check" {
        return result;
    }

    let mut unsafe_findings: Vec<Diagnostic> = Vec::new();
    for (path, (snapshot, content)) in paths.iter().zip(&files) {
        let Some(diagnostic) = &content.diagnostic else {
            continue;
        };
        if diagnostic.code != "LMH004" {
            continue;
        }
        let repaired = match (&snapshot.unsafe_reason, &content.replacement) {
            (Some(reason), _) => Err(RepairError::Unsafe(reason.clone())),
            (None, Some(bytes)) => {
                filesystem::replace(path, snapshot, bytes, &settings.project_root)
            }
            (None, None) => Err(RepairError::Unsafe(
                "copyright bytes cannot be repaired safely".into(),
            )),
        };
        match repaired {
            Ok(()) => {
                result.changed.push(diagnostic.path.clone());
                result.diagnostics.retain(|d| d.path != diagnostic.path);
            }
            Err(RepairError::Unsafe(reason)) => {
                let mut unsafe_diagnostic = diagnostic.clone();
                unsafe_diagnostic.code = "LMH008".into();
                unsafe_diagnostic.message = reason;
                unsafe_diagnostic.fixable = false;
                if let Some(existing) = result
                    .diagnostics
                    .iter_mut()
                    .find(|d| d.path == diagnostic.path)
                {
                    *existing = unsafe_diagnostic.clone();
                }
                unsafe_findings.push(unsafe_diagnostic);
            }
            Err(RepairError::Io(error)) => {
                result.fail(error, Some(diagnostic.path.clone()));
                return result;
            }
        }
    }

    // Recheck through the same analyzer: the report describes the files after fix.
    result.diagnostics.clear();
    for path in &paths {
        let shown = display_path(path, &settings.project_root);
        if let Some(diagnostic) = unsafe_findings.iter().find(|d| d.path == shown) {
            result.diagnostics.push(diagnostic.clone());
            continue;
        }
        match filesystem::read(path, &settings.project_root) {
            Ok(snapshot) => {
                if let Some(mut diagnostic) =
                    analysis::analyze(&snapshot.bytes, &policy, &shown).diagnostic
                {
                    diagnostic.fixable &= snapshot.unsafe_reason.is_none();
                    result.diagnostics.push(diagnostic);
                }
            }
            Err(error) => {
                result.fail(error, Some(shown));
                return result;
            }
        }
    }
    result
}

fn write_action_outputs(result: &CommandResult) -> io::Result<()> {
    let Some(path) = std::env::var_os("GITHUB_OUTPUT") else {
        return Ok(());
    };
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)?;
    let mut issues: Vec<&str> = if result.error.is_some() {
        Vec::new()
    } else {
        result.diagnostics.iter().map(|d| d.path.as_str()).collect()
    };
    issues.sort_unstable();
    issues.dedup();
    writeln!(file, "issues={}", serde_json::to_string(&issues)?)?;
    writeln!(file, "changed={}", serde_json::to_string(&result.changed)?)
}

fn render(result: &CommandResult, format: OutputFormat) -> io::Result<()> {
    let mut stdout = io::stdout().lock();
    if format == OutputFormat::Json {
        serde_json::to_writer(&mut stdout, result)?;
        return writeln!(stdout);
    }
    if !result.changed.is_empty() {
        writeln!(stdout, "Updated headers:")?;
        for path in &result.changed {
            writeln!(stdout, "- {path}")?;
        }
    }
    let mut stderr = io::stderr().lock();
    if let Some(error) = &result.error {
        let path = error
            .path
            .as_ref()
            .map(|p| format!(" ({p})"))
            .unwrap_or_default();
        writeln!(stderr, "error: {}{path}", error.message)?;
    }
    for diagnostic in &result.diagnostics {
        let suffix = if diagnostic.fixable { " [fixable]" } else { "" };
        writeln!(
            stderr,
            "{}:{}:{}: {} {}{suffix}",
            diagnostic.path,
            diagnostic.line,
            diagnostic.column,
            diagnostic.code,
            diagnostic.message
        )?;
    }
    if !result.diagnostics.is_empty()
        && let Some(header) = &result.expected_header
    {
        writeln!(stderr, "\nExpected header:\n\n{header}")?;
    }
    Ok(())
}

pub fn main_entry() -> i32 {
    static VERSION: std::sync::OnceLock<String> = std::sync::OnceLock::new();
    let command = Cli::command().version(VERSION.get_or_init(version).as_str());
    let args = Cli::from_arg_matches(&command.get_matches()).expect("clap-validated arguments");
    let options = args.command.options();
    let explicit_config = options
        .config
        .as_ref()
        .map(|p| display_path(p, &std::env::current_dir().unwrap_or_default()));
    let mut result = match config::resolve(options) {
        Ok(settings) => {
            let mut result = run(&settings, args.command.name(), chrono::Local::now().year());
            if result.expected_header.is_none() && result.error.is_some() {
                result.config_path = explicit_config.clone();
                if let Some(error) = &mut result.error
                    && error.message.starts_with("Unable to locate")
                {
                    error.path = explicit_config.clone();
                }
            }
            result
        }
        Err(error) => {
            let mut result = CommandResult::new(args.command.name());
            let path = if error.starts_with("Invalid configuration path:") {
                explicit_config.clone()
            } else {
                None
            };
            result.config_path = explicit_config;
            result.fail(error, path);
            result
        }
    };
    if let Err(error) = write_action_outputs(&result) {
        result.fail(
            format!("Unable to write GitHub Action outputs: {error}"),
            None,
        );
    }
    if let Err(error) = render(&result, options.output_format) {
        if error.kind() != io::ErrorKind::BrokenPipe {
            eprintln!("error: {error}");
        }
        return 2;
    }
    result.exit_code()
}
