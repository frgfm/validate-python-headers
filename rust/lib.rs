pub mod analysis;
pub mod config;
pub mod filesystem;
pub mod model;

use chrono::Datelike;
use clap::{CommandFactory, FromArgMatches};
use config::{Cli, OutputFormat};
use filesystem::RepairError;
use model::{CommandResult, Settings};
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
            std::env::current_dir()
                .and_then(|cwd| cwd.canonicalize())
                .unwrap_or_default()
                .join(path)
        };
        let mut normal = PathBuf::new();
        for part in path.components() {
            match part {
                #[cfg(windows)]
                Component::Prefix(prefix) => match prefix.kind() {
                    std::path::Prefix::VerbatimDisk(drive) => {
                        normal.push(format!("{}:", char::from(drive)));
                    }
                    std::path::Prefix::VerbatimUNC(server, share) => {
                        normal.push(r"\\");
                        normal.push(server);
                        normal.push(share);
                    }
                    _ => normal.push(prefix.as_os_str()),
                },
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
    let outcome: Result<(), (String, Option<String>)> = (|| {
        let policy = analysis::build_policy(settings, current_year).map_err(|e| (e, None))?;
        result.expected_header = Some(policy.expected_header.clone());
        let mut paths = filesystem::discover(settings).map_err(|e| (e, None))?;
        paths.sort_by_key(|p| display_path(p, &settings.project_root));
        let read = |path: &Path| {
            let shown = display_path(path, &settings.project_root);
            let snapshot = filesystem::read(path, &settings.project_root)
                .map_err(|e| (e.to_string(), Some(shown.clone())))?;
            let mut content = analysis::analyze(&snapshot.bytes, &policy, &shown);
            if let Some(diagnostic) = &mut content.diagnostic {
                diagnostic.fixable &= snapshot.unsafe_reason.is_none();
            }
            Ok::<_, (String, Option<String>)>((snapshot, content))
        };
        let mut files = Vec::with_capacity(paths.len());
        for path in &paths {
            let file = read(path)?;
            result.diagnostics.extend(file.1.diagnostic.clone());
            result.checked += 1;
            files.push(file);
        }
        if command != "fix" {
            return Ok(());
        }
        let repaired = paths
            .iter()
            .zip(&mut files)
            .try_for_each(|(path, (snapshot, content))| {
                let Some(diagnostic) = &mut content.diagnostic else {
                    return Ok(());
                };
                if diagnostic.code != "LMH004" {
                    return Ok(());
                }
                let repair = match (&snapshot.unsafe_reason, &content.replacement) {
                    (Some(reason), _) => Err(RepairError::Unsafe(reason.clone())),
                    (None, Some(bytes)) => {
                        filesystem::replace(path, snapshot, bytes, &settings.project_root)
                    }
                    (None, None) => Err(RepairError::Unsafe(
                        "copyright bytes cannot be repaired safely".into(),
                    )),
                };
                match repair {
                    Ok(()) => {
                        result.changed.push(diagnostic.path.clone());
                        content.diagnostic = None;
                    }
                    Err(RepairError::Unsafe(reason)) => {
                        diagnostic.code = "LMH008".into();
                        diagnostic.message = reason;
                        diagnostic.fixable = false;
                    }
                    Err(RepairError::Io(error)) => {
                        return Err((error.to_string(), Some(diagnostic.path.clone())));
                    }
                }
                Ok(())
            });
        result.diagnostics = files
            .iter()
            .filter_map(|file| file.1.diagnostic.clone())
            .collect();
        repaired?;
        // Keep unsafe findings; otherwise report the files as they stand after repair.
        result.diagnostics.clear();
        for (path, (_, content)) in paths.iter().zip(files) {
            let diagnostic = match content.diagnostic {
                Some(d) if d.code == "LMH008" => Some(d),
                _ => read(path)?.1.diagnostic,
            };
            result.diagnostics.extend(diagnostic);
        }
        Ok(())
    })();
    if let Err((message, path)) = outcome {
        result.fail(message, path);
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
