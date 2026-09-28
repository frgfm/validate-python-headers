use crate::model::Settings;
use clap::{Args, Parser, Subcommand, ValueEnum};
use std::path::{Path, PathBuf};
use toml::{Table, Value};

const SECTION: &str = "[tool.lint-my-headers]";
const KEYS: &[&str] = &[
    "owner",
    "starting-year",
    "license",
    "license-notice",
    "paths",
    "ignore-files",
    "ignore-folders",
];

#[derive(Parser, Debug)]
#[command(
    name = "lmh",
    about = "Lint Python copyright and license headers and conservatively refresh recognized years."
)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Command,
}

#[derive(Subcommand, Debug)]
pub enum Command {
    /// Check copyright and license headers without writing source files.
    Check(Options),
    /// Safely refresh only recognized stale copyright years.
    Fix(Options),
}

impl Command {
    pub fn name(&self) -> &'static str {
        match self {
            Self::Check(_) => "check",
            Self::Fix(_) => "fix",
        }
    }
    pub fn options(&self) -> &Options {
        match self {
            Self::Check(o) | Self::Fix(o) => o,
        }
    }
}

#[derive(Clone, Copy, Debug, ValueEnum, PartialEq, Default)]
pub enum OutputFormat {
    #[default]
    Text,
    Json,
}

#[derive(Args, Debug, Default)]
pub struct Options {
    #[arg(long, help = "Path to pyproject.toml; defaults to the nearest one")]
    pub config: Option<PathBuf>,
    #[arg(long)]
    pub owner: Option<String>,
    #[arg(long, allow_negative_numbers = true)]
    pub starting_year: Option<i32>,
    #[arg(long)]
    pub license: Option<String>,
    #[arg(long)]
    pub license_notice: Option<PathBuf>,
    #[arg(long, hide = true)]
    pub folders: Option<String>,
    #[arg(long)]
    pub ignore_files: Option<String>,
    #[arg(long)]
    pub ignore_folders: Option<String>,
    #[arg(long, value_enum, default_value = "text")]
    pub output_format: OutputFormat,
    /// Explicit files or folders; overrides configured paths.
    pub paths: Vec<PathBuf>,
}

fn find_config(explicit: Option<&Path>, cwd: &Path) -> Result<Option<PathBuf>, String> {
    if let Some(path) = explicit {
        if !path.is_file() {
            return Err(format!("Invalid configuration path: {}", path.display()));
        }
        return path.canonicalize().map(Some).map_err(|e| e.to_string());
    }
    for parent in cwd.ancestors() {
        let candidate = parent.join("pyproject.toml");
        if candidate.is_file() {
            return candidate
                .canonicalize()
                .map(Some)
                .map_err(|e| e.to_string());
        }
    }
    Ok(None)
}

fn config_table(path: &Path) -> Result<Table, String> {
    let content = std::fs::read_to_string(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let doc: Table = toml::from_str(&content).map_err(|e| e.to_string())?;
    let Some(tool) = doc.get("tool") else {
        return Ok(Table::new());
    };
    let tool = tool
        .as_table()
        .ok_or_else(|| format!("Invalid [tool]: expected a table in {}", path.display()))?;
    let Some(config) = tool.get("lint-my-headers") else {
        return Ok(Table::new());
    };
    let config = config
        .as_table()
        .ok_or_else(|| format!("Invalid {SECTION}: expected a table in {}", path.display()))?;
    for (key, value) in config {
        let invalid = |reason| format!("Invalid {SECTION}.{key}: {reason} in {}", path.display());
        if !KEYS.contains(&key.as_str()) {
            return Err(invalid("unknown key"));
        }
        match key.as_str() {
            "owner" | "license" | "license-notice" => {
                if value.as_str().is_none_or(str::is_empty) {
                    return Err(invalid("expected a non-empty string"));
                }
            }
            "starting-year" => {
                if value
                    .as_integer()
                    .is_none_or(|v| !(1000..=9999).contains(&v))
                {
                    return Err(invalid("expected a four-digit integer"));
                }
            }
            _ => {
                let Some(items) = value.as_array() else {
                    return Err(invalid("expected an array of non-empty strings"));
                };
                if items.iter().any(|v| v.as_str().is_none_or(str::is_empty)) {
                    return Err(invalid("expected an array of non-empty strings"));
                }
                if key == "paths" && items.is_empty() {
                    return Err(invalid("expected at least one path"));
                }
            }
        }
    }
    Ok(config.clone())
}

fn strings(table: &Table, key: &str, default: &[&str]) -> Vec<String> {
    table
        .get(key)
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(Value::as_str)
                .map(str::to_owned)
                .collect()
        })
        .unwrap_or_else(|| default.iter().map(|s| (*s).into()).collect())
}

fn split_values(value: &str) -> Vec<String> {
    value
        .split(',')
        .map(str::trim)
        .filter(|v| !v.is_empty())
        .map(str::to_owned)
        .collect()
}

pub fn resolve(options: &Options) -> Result<Settings, String> {
    let cwd = std::env::current_dir().map_err(|e| e.to_string())?;
    let config_path = find_config(options.config.as_deref(), &cwd)?;
    let table = match &config_path {
        Some(path) => config_table(path)?,
        None => Table::new(),
    };
    let root = config_path
        .as_ref()
        .and_then(|p| p.parent())
        .unwrap_or(&cwd)
        .to_path_buf();
    let string = |key| table.get(key).and_then(Value::as_str).map(str::to_owned);
    let owner = options
        .owner
        .clone()
        .or_else(|| string("owner"))
        .filter(|s| !s.is_empty())
        .ok_or_else(|| {
            format!("Missing {SECTION}.owner; set it in pyproject.toml or pass --owner")
        })?;
    let year = options
        .starting_year
        .or_else(|| {
            table
                .get("starting-year")
                .and_then(Value::as_integer)
                .and_then(|i| i32::try_from(i).ok())
        })
        .ok_or_else(|| {
            format!(
                "Missing {SECTION}.starting-year; set it in pyproject.toml or pass --starting-year"
            )
        })?;
    let (license, notice) = if options.license.is_some() || options.license_notice.is_some() {
        (options.license.clone(), options.license_notice.clone())
    } else {
        (
            string("license"),
            string("license-notice").map(|s| root.join(s)),
        )
    };
    let license = license.filter(|s| !s.is_empty());
    let notice = notice.filter(|p| !p.as_os_str().is_empty());
    if license.is_some() == notice.is_some() {
        return Err(format!(
            "Configure exactly one of {SECTION}.license or {SECTION}.license-notice, or pass one matching CLI option"
        ));
    }
    if !options.paths.is_empty() && options.folders.is_some() {
        return Err("Pass explicit paths or --folders, not both".into());
    }
    let paths = if !options.paths.is_empty() {
        options.paths.clone()
    } else if let Some(folders) = &options.folders {
        split_values(folders).iter().map(PathBuf::from).collect()
    } else {
        strings(&table, "paths", &["."])
            .iter()
            .map(|s| root.join(s))
            .collect()
    };
    if paths.is_empty() {
        return Err(format!(
            "Invalid {SECTION}.paths: expected at least one path"
        ));
    }
    let ignore_files = options
        .ignore_files
        .as_deref()
        .map(split_values)
        .unwrap_or_else(|| strings(&table, "ignore-files", &["__init__.py"]));
    let ignore_folders = options
        .ignore_folders
        .as_deref()
        .map(|s| split_values(s).iter().map(PathBuf::from).collect())
        .unwrap_or_else(|| {
            strings(&table, "ignore-folders", &[".github"])
                .iter()
                .map(|s| root.join(s))
                .collect()
        });
    Ok(Settings {
        owner,
        year,
        license,
        license_notice: notice,
        license_path: root.join("LICENSE"),
        paths,
        ignore_files,
        ignore_folders,
        project_root: root,
        config_path,
    })
}
