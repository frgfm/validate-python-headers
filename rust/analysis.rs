use crate::model::{Diagnostic, HeaderPolicy, Settings};
use regex::Regex;
use rustpython_parser::{Mode, Tok, lexer};
use serde_json::Value;
use std::{fs, sync::LazyLock};

static COPYRIGHT: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^# Copyright \(C\) (?P<years>(?P<start>[0-9]{4})(?:-(?P<end>[0-9]{4}))?), (?P<owner>.*)\.$")
        .expect("valid copyright expression")
});
static CODING: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^[ \t\x0c]*#.*?coding[:=][ \t]*([-_.a-zA-Z0-9]+)")
        .expect("valid encoding expression")
});
static SPDX: LazyLock<Value> = LazyLock::new(|| {
    serde_json::from_str(include_str!(
        "../src/lint_my_headers/supported-licenses.json"
    ))
    .expect("valid bundled SPDX data")
});
static LEGACY: LazyLock<Value> = LazyLock::new(|| {
    serde_json::from_str(include_str!(
        "../src/lint_my_headers/legacy-license-notices.json"
    ))
    .expect("valid bundled legacy SPDX data")
});

fn normalize_newlines(source: &str) -> String {
    source.replace("\r\n", "\n").replace('\r', "\n")
}

pub fn build_policy(settings: &Settings, current_year: i32) -> Result<HeaderPolicy, String> {
    if settings.year < 1000 || settings.year > current_year {
        return Err(format!("Invalid first copyright year: {}", settings.year));
    }
    if settings.owner.is_empty() || settings.owner.contains(['\n', '\r']) {
        return Err("Please specify a single-line copyright owner".into());
    }
    let mut notices = Vec::new();
    if let Some(id) = settings.license.as_ref().filter(|id| !id.is_empty()) {
        if !settings.license_path.is_file() {
            return Err("Unable to locate local copy of license text.".into());
        }
        let current = SPDX["licenses"]
            .as_array()
            .expect("bundled licenses array")
            .iter()
            .find(|entry| entry["licenseId"] == *id);
        for (entry, urls_key) in [(LEGACY["licenses"].get(id), "urls"), (current, "seeAlso")] {
            let Some(entry) = entry else { continue };
            let name = entry["name"].as_str().expect("bundled license name");
            let urls = entry[urls_key].as_array().expect("bundled license URLs");
            let fallback = format!("https://spdx.org/licenses/{id}.html");
            let urls: Vec<&str> = if urls.is_empty() {
                vec![&fallback]
            } else {
                urls.iter()
                    .map(|url| url.as_str().expect("bundled URL"))
                    .collect()
            };
            for url in urls {
                let notice = format!(
                    "# This program is licensed under the {name}.\n\
                     # See LICENSE or go to <{url}> for full license details.\n"
                );
                if !notices.contains(&notice) {
                    notices.push(notice);
                }
            }
        }
        if notices.is_empty() {
            return Err(format!("Invalid license identifier: {id}"));
        }
    } else if let Some(path) = &settings.license_notice {
        if !path.is_file() {
            return Err("Unable to locate the text of the license notice.".into());
        }
        notices.push(normalize_newlines(
            &fs::read_to_string(path).map_err(|e| e.to_string())?,
        ));
    } else {
        return Err(
            "One of the following args needs to be specified: 'license', 'license-notice'".into(),
        );
    }
    let years = if settings.year == current_year {
        current_year.to_string()
    } else {
        format!("<FILE_CREATION_YEAR>-{current_year}")
    };
    Ok(HeaderPolicy {
        owner: settings.owner.clone(),
        starting_year: settings.year,
        current_year,
        expected_header: format!(
            "# Copyright (C) {years}, {}.\n\n{}",
            settings.owner, notices[0]
        ),
        license_notices: notices,
    })
}

pub struct ContentAnalysis {
    pub diagnostic: Option<Diagnostic>,
    pub replacement: Option<Vec<u8>>,
}

fn problem(path: &str, line: usize, code: &str, message: impl Into<String>) -> ContentAnalysis {
    ContentAnalysis {
        diagnostic: Some(Diagnostic {
            path: path.into(),
            line: line.max(1),
            column: 1,
            code: code.into(),
            message: message.into(),
            fixable: false,
        }),
        replacement: None,
    }
}

fn comment_or_blank(line: &str) -> bool {
    line.trim_start_matches([' ', '\t', '\x0c'])
        .starts_with(['#', '\r', '\n'])
        || line.trim_matches([' ', '\t', '\x0c']).is_empty()
}

fn encoding_cookie(line: &[u8]) -> Result<Option<String>, String> {
    // Python detects cookies by decoding each of the first two physical lines as UTF-8.
    let line = std::str::from_utf8(line).map_err(|_| "invalid or missing encoding declaration")?;
    Ok(CODING.captures(line).map(|captures| {
        let label = captures[1].to_ascii_lowercase().replace('_', "-");
        let prefix = &label[..label.len().min(12)];
        if prefix == "utf-8" || prefix.starts_with("utf-8-") {
            "utf-8".into()
        } else if matches!(prefix, "latin-1" | "iso-8859-1" | "iso-latin-1")
            || prefix.starts_with("latin-1-")
            || prefix.starts_with("iso-8859-1-")
            || prefix.starts_with("iso-latin-1-")
        {
            "latin-1".into()
        } else {
            label
        }
    }))
}

fn decode_source(raw: &[u8]) -> Result<String, String> {
    let bom = raw.starts_with(b"\xef\xbb\xbf");
    let raw = if bom { &raw[3..] } else { raw };
    let mut lines = raw.split_inclusive(|byte| *byte == b'\n');
    let first = lines.next().unwrap_or_default();
    let mut cookie = encoding_cookie(first)?;
    if cookie.is_none() && comment_or_blank(std::str::from_utf8(first).unwrap_or_default()) {
        cookie = encoding_cookie(lines.next().unwrap_or_default())?;
    }
    let label = cookie.as_deref().unwrap_or("utf-8");
    if bom && label != "utf-8" {
        return Err("encoding problem: utf-8".into());
    }
    match label {
        "utf-8" | "utf8" | "u8" | "utf" | "cp65001" | "utf8-ucs2" | "utf8-ucs4" => {
            return String::from_utf8(raw.to_vec()).map_err(|e| e.to_string());
        }
        "ascii" | "us-ascii" | "646" | "ansi-x3.4-1968" | "ansi-x3.4-1986" | "ansi-x3-4-1968"
        | "cp367" | "csascii" | "ibm367" | "iso646-us" | "iso-646.irv-1991" | "iso-ir-6" | "us" => {
            return if raw.is_ascii() {
                Ok(String::from_utf8(raw.to_vec()).expect("ASCII is UTF-8"))
            } else {
                Err("invalid byte in ASCII source".into())
            };
        }
        "latin-1" | "latin1" | "iso8859-1" | "iso-8859-1" | "l1" | "8859" | "cp819" | "ibm819"
        | "csisolatin1" | "iso8859" | "iso-ir-100" | "latin" => {
            return Ok(raw.iter().map(|byte| char::from(*byte)).collect());
        }
        "cp1252" | "windows-1252" | "1252" => {}
        _ => return Err(format!("unsupported source encoding: {label}")),
    }
    // Python rejects the five undefined Windows-1252 byte values.
    if raw
        .iter()
        .any(|b| matches!(b, 0x81 | 0x8d | 0x8f | 0x90 | 0x9d))
    {
        return Err("undefined byte in Windows-1252 source".into());
    }
    const CP1252_EXTENDED: [char; 32] = [
        '€', '\0', '‚', 'ƒ', '„', '…', '†', '‡', 'ˆ', '‰', 'Š', '‹', 'Œ', '\0', 'Ž', '\0', '\0',
        '‘', '’', '“', '”', '•', '–', '—', '˜', '™', 'š', '›', 'œ', '\0', 'ž', 'Ÿ',
    ];
    Ok(raw
        .iter()
        .map(|&byte| {
            if (0x80..=0x9f).contains(&byte) {
                CP1252_EXTENDED[usize::from(byte - 0x80)]
            } else {
                char::from(byte)
            }
        })
        .collect())
}

fn preamble(lines: &[&str]) -> (usize, bool) {
    let shebang = usize::from(lines.first().is_some_and(|line| line.starts_with("#!")));
    let cookie_end = if lines.first().is_some_and(|line| CODING.is_match(line)) {
        1
    } else if lines.len() > 1 && comment_or_blank(lines[0]) && CODING.is_match(lines[1]) {
        2
    } else {
        0
    };
    let end = shebang.max(cookie_end);
    if end == 0 {
        return (0, true);
    }
    let separator = lines
        .get(end)
        .is_some_and(|line| line.trim_end_matches(['\r', '\n']).is_empty());
    (end + usize::from(separator), separator)
}

fn expression_may_contain_copyright(value: &str) -> bool {
    let bytes = value.as_bytes();
    let mut depth = 0usize;
    let mut index = 0;
    while index < bytes.len() {
        if depth == 0 && (bytes[index..].starts_with(b"{{") || bytes[index..].starts_with(b"}}")) {
            index += 2;
            continue;
        }
        match bytes[index] {
            b'{' => depth += 1,
            b'}' => depth = depth.saturating_sub(1),
            // Do not mistake a brace inside an expression's string or comment for its end.
            b'\'' | b'"' | b'#' if depth > 0 => return value[index..].contains("# Copyright"),
            _ => {}
        }
        index += 1;
    }
    false
}

pub fn analyze(raw: &[u8], policy: &HeaderPolicy, display_path: &str) -> ContentAnalysis {
    let source = match decode_source(raw) {
        Ok(source) => source,
        Err(error) => {
            return problem(
                display_path,
                1,
                "LMH007",
                format!("unable to decode Python source: {error}"),
            );
        }
    };
    // The Python tokenizer does not treat bare CR as a physical line boundary.
    // Normalizing one could turn an ambiguous header into an authorized repair.
    let bare_cr =
        source.as_bytes().iter().enumerate().any(|(index, byte)| {
            *byte == b'\r' && source.as_bytes().get(index + 1) != Some(&b'\n')
        });
    let source = normalize_newlines(&source);
    let lines: Vec<&str> = source.split_inclusive('\n').collect();
    let (header_index, separator_valid) = preamble(&lines);
    let mut prefixes = Vec::new();
    let mut matches = Vec::new();
    let mut offset = 0;
    let mut line_index = 0;
    let mut ambiguous_tail = false;
    let mut template_prefix_end = None;
    for token in lexer::lex(&source, Mode::Module) {
        let (token, range) = match token {
            Ok(token) => token,
            Err(error) => {
                // An incomplete scan cannot establish that later copyright text is harmless.
                ambiguous_tail |= source
                    .get(usize::from(error.location)..)
                    .unwrap_or(&source)
                    .contains("# Copyright");
                break;
            }
        };
        let start: usize = range.start().into();
        if let Tok::String { value, kind, .. } = &token {
            // Older lexers hide PEP 701/750 expression comments inside string tokens.
            ambiguous_tail |= (kind.is_any_fstring() || template_prefix_end == Some(start))
                && expression_may_contain_copyright(value);
        }
        template_prefix_end = match &token {
            Tok::Name { name }
                if matches!(name.to_ascii_lowercase().as_str(), "t" | "tr" | "rt") =>
            {
                Some(usize::from(range.end()))
            }
            _ => None,
        };
        if let Tok::Comment(comment) = token {
            line_index += source[offset..start]
                .bytes()
                .filter(|byte| *byte == b'\n')
                .count();
            offset = start;
            if comment.starts_with("# Copyright") {
                prefixes.push(line_index);
            }
            if COPYRIGHT.is_match(&comment) {
                matches.push((line_index, comment));
            }
        }
    }
    if header_index >= lines.len() || prefixes.is_empty() {
        return problem(
            display_path,
            header_index + 1,
            "LMH001",
            "missing legal header",
        );
    }
    if bare_cr
        || ambiguous_tail
        || !separator_valid
        || prefixes.len() != 1
        || matches.len() != 1
        || matches[0].0 != header_index
    {
        return problem(
            display_path,
            prefixes[0] + 1,
            "LMH006",
            "malformed, misplaced, or ambiguous header",
        );
    }
    let (line_index, comment) = &matches[0];
    let captures = COPYRIGHT
        .captures(comment)
        .expect("matched copyright comment");
    if captures["owner"] != policy.owner {
        return problem(
            display_path,
            line_index + 1,
            "LMH002",
            format!(
                "copyright owner is '{}'; expected '{}'",
                &captures["owner"], policy.owner
            ),
        );
    }
    let start_year: i32 = captures["start"].parse().expect("four ASCII digits");
    let end_year = captures
        .name("end")
        .map(|year| year.as_str().parse::<i32>().expect("four ASCII digits"));
    if start_year < policy.starting_year
        || start_year > policy.current_year
        || end_year.is_some_and(|end| end < start_year || end > policy.current_year)
    {
        return problem(
            display_path,
            line_index + 1,
            "LMH003",
            format!(
                "copyright year '{}' is outside the accepted range",
                &captures["years"]
            ),
        );
    }
    let blank_index = line_index + 1;
    if !lines
        .get(blank_index)
        .is_some_and(|line| line.trim_end_matches('\n').is_empty())
    {
        return problem(
            display_path,
            blank_index + 1,
            "LMH006",
            "expected one blank line between copyright and license notice",
        );
    }
    let notice_source = lines[blank_index + 1..].concat();
    if !policy
        .license_notices
        .iter()
        .any(|notice| notice_source.starts_with(notice))
    {
        return problem(
            display_path,
            blank_index + 2,
            "LMH005",
            "missing or mismatched license notice",
        );
    }
    let last_year = end_year.unwrap_or(start_year);
    if last_year == policy.current_year {
        return ContentAnalysis {
            diagnostic: None,
            replacement: None,
        };
    }
    let mut result = problem(
        display_path,
        line_index + 1,
        "LMH004",
        format!(
            "copyright year ends at {last_year}; expected {}",
            policy.current_year
        ),
    );
    // Splice only the ASCII year bytes. The original encoding, preamble and body stay untouched.
    let needle = format!("# Copyright (C) {}, ", &captures["years"]);
    let raw_lines: Vec<&[u8]> = raw.split_inclusive(|byte| *byte == b'\n').collect();
    if let Some(raw_line) = raw_lines.get(*line_index) {
        let offsets: Vec<usize> = raw_line
            .windows(needle.len())
            .enumerate()
            .filter_map(|(index, bytes)| (bytes == needle.as_bytes()).then_some(index))
            .collect();
        if offsets.len() == 1 {
            let year_start = raw_lines[..*line_index]
                .iter()
                .map(|line| line.len())
                .sum::<usize>()
                + offsets[0]
                + b"# Copyright (C) ".len();
            let mut repaired = raw[..year_start].to_vec();
            repaired.extend_from_slice(format!("{start_year}-{}", policy.current_year).as_bytes());
            repaired.extend_from_slice(&raw[year_start + captures["years"].len()..]);
            if analyze(&repaired, policy, display_path)
                .diagnostic
                .is_none()
            {
                result.replacement = Some(repaired);
                result
                    .diagnostic
                    .as_mut()
                    .expect("stale diagnostic")
                    .fixable = true;
            }
        }
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    fn policy() -> HeaderPolicy {
        HeaderPolicy {
            owner: "Example Owner".into(),
            starting_year: 2022,
            current_year: 2030,
            license_notices: vec!["# License notice.\n".into()],
            expected_header: String::new(),
        }
    }

    fn header(years: &str) -> String {
        format!("# Copyright (C) {years}, Example Owner.\n\n# License notice.\n\nvalue = 'café'\n")
    }

    #[test]
    fn policy_keeps_every_legacy_notice_and_rejects_invalid_settings() {
        let license = tempfile::NamedTempFile::new().unwrap();
        let mut settings = Settings {
            owner: "Example Owner".into(),
            year: 2022,
            license: None,
            license_notice: None,
            license_path: license.path().into(),
            paths: Vec::new(),
            ignore_files: Vec::new(),
            ignore_folders: Vec::new(),
            project_root: std::env::temp_dir(),
            config_path: None,
        };
        assert!(build_policy(&settings, 2030).is_err());
        for (id, entry) in LEGACY["licenses"].as_object().unwrap() {
            settings.license = Some(id.clone());
            let policy = build_policy(&settings, 2030).unwrap();
            let name = entry["name"].as_str().unwrap();
            for url in entry["urls"].as_array().unwrap() {
                let expected = format!(
                    "# This program is licensed under the {name}.\n\
                     # See LICENSE or go to <{}> for full license details.\n",
                    url.as_str().unwrap()
                );
                assert!(policy.license_notices.contains(&expected), "{id}");
            }
        }
        settings.license = Some("not-an-SPDX-license".into());
        assert!(
            build_policy(&settings, 2030)
                .unwrap_err()
                .starts_with("Invalid license identifier:")
        );
        settings.year = 2031;
        assert!(
            build_policy(&settings, 2030)
                .unwrap_err()
                .starts_with("Invalid first copyright year:")
        );
        settings.year = 2030;
        settings.license = Some("Apache-2.0".into());
        assert!(
            build_policy(&settings, 2030)
                .unwrap()
                .expected_header
                .starts_with("# Copyright (C) 2030, Example Owner.")
        );
        settings.owner = "Two\nLines".into();
        assert!(build_policy(&settings, 2030).is_err());
    }

    #[test]
    fn only_verified_python_encodings_are_decoded() {
        assert_eq!(
            decode_source(b"# coding: cp1252\n\n# \x80\n").unwrap(),
            "# coding: cp1252\n\n# €\n"
        );
        for label in [
            "utf-7",
            "cp932",
            "shift_jis",
            "iso-8859-9",
            "cp1250",
            "cp1251",
        ] {
            let raw = format!("# coding: {label}\n\n{}", header("2024"));
            let result = analyze(raw.as_bytes(), &policy(), "x.py");
            assert_eq!(result.diagnostic.unwrap().code, "LMH007");
            assert!(result.replacement.is_none());
        }
    }

    #[test]
    fn diagnostics_and_precedence() {
        let valid = header("2030");
        assert!(
            analyze(valid.as_bytes(), &policy(), "x.py")
                .diagnostic
                .is_none()
        );
        let cases = [
            ("value = 1\n".into(), "LMH001", 1),
            (
                header("2024").replace("Example Owner", "Someone Else"),
                "LMH002",
                1,
            ),
            (header("2031"), "LMH003", 1),
            (header("2024"), "LMH004", 1),
            (
                header("2024").replace("# License notice.", "# Wrong."),
                "LMH005",
                3,
            ),
            (header("20x4"), "LMH006", 1),
            (format!("# coding: made-up-codec\n\n{valid}"), "LMH007", 1),
            (header("2024").replacen("\n\n", "\n", 1), "LMH006", 2),
            (format!("#!/usr/bin/python\n{valid}"), "LMH006", 2),
        ];
        for (source, code, line) in cases {
            let result = analyze(source.as_bytes(), &policy(), "x.py");
            let diagnostic = result.diagnostic.unwrap();
            assert_eq!(diagnostic.code, code, "{source}");
            assert_eq!(diagnostic.line, line, "{source}");
            assert_eq!(diagnostic.fixable, code == "LMH004");
            assert_eq!(result.replacement.is_some(), code == "LMH004");
        }
    }

    #[test]
    fn only_real_comments_count() {
        for literal in [
            "\"\"\"\n# Copyright (C) 2024, Other.\n\"\"\"",
            "'''\n# Copyright (C) 2024, Other.\n'''",
            "r'\"# Copyright (C) 2024, Other.\"'",
        ] {
            let source = format!("{}\nEXAMPLE = {literal}\n", header("2030"));
            assert!(
                analyze(source.as_bytes(), &policy(), "x.py")
                    .diagnostic
                    .is_none()
            );
        }
        let duplicate = format!("{}\n# Copyright (C) 2024, Other.\n", header("2030"));
        assert_eq!(
            analyze(duplicate.as_bytes(), &policy(), "x.py")
                .diagnostic
                .unwrap()
                .code,
            "LMH006"
        );
        let example =
            "EXAMPLE = '''\n# Copyright (C) 2030, Example Owner.\n\n# License notice.\n'''\n";
        assert_eq!(
            analyze(example.as_bytes(), &policy(), "x.py")
                .diagnostic
                .unwrap()
                .code,
            "LMH001"
        );
    }

    #[test]
    fn repairs_preserve_bom_preambles_crlf_encoding_and_body() {
        for preamble in [
            "",
            "#!/usr/bin/env python3\n\n",
            "# coding: utf-8\n\n",
            "#!/usr/bin/env python3\n# coding: utf-8\n\n",
        ] {
            let raw = format!("\u{feff}{preamble}{}", header("2024"))
                .replace('\n', "\r\n")
                .into_bytes();
            let fixed = analyze(&raw, &policy(), "x.py").replacement.unwrap();
            assert_eq!(
                fixed,
                String::from_utf8(raw)
                    .unwrap()
                    .replacen("2024", "2024-2030", 1)
                    .as_bytes()
            );
            assert!(analyze(&fixed, &policy(), "x.py").diagnostic.is_none());
        }
        let text = format!("# coding: latin-1\n\n{}", header("2024"));
        let raw: Vec<u8> = text.chars().map(|c| c as u8).collect();
        let repaired = analyze(&raw, &policy(), "latin.py").replacement.unwrap();
        let expected: Vec<u8> = text
            .replacen("2024", "2024-2030", 1)
            .chars()
            .map(|c| c as u8)
            .collect();
        assert_eq!(repaired, expected);
        assert_eq!(
            decode_source(b"# coding: latin-1\n\n# \x80\n").unwrap(),
            "# coding: latin-1\n\n# \u{80}\n"
        );
    }

    #[test]
    fn encoding_failures_never_offer_repair() {
        for raw in [
            b"\xef\xbb\xbf# coding: latin-1\n".as_slice(),
            b"# coding: ascii\n\n# \xff\n",
            b"# coding: utf-8\n\n# \xff\n",
            b"# coding: cp1252\n\n# \x81\n",
            b"# coding: cp1250\n\n# \x81\n",
            b"# coding: cp1251\n\n# \x98\n",
            b"# coding: iso-8859-9\n\n# \x80\n",
            b"# coding: latin-1 \xff\n",
        ] {
            let result = analyze(raw, &policy(), "x.py");
            assert_eq!(result.diagnostic.unwrap().code, "LMH007");
            assert!(result.replacement.is_none());
        }
        let source = format!("value = 0\n# coding: utf-8\n\n{}", header("2030"));
        assert_eq!(
            analyze(source.as_bytes(), &policy(), "x.py")
                .diagnostic
                .unwrap()
                .code,
            "LMH006"
        );
    }

    #[test]
    fn bare_carriage_returns_do_not_authorize_a_repair() {
        for years in ["2024", "2030"] {
            let source = header(years).replace('\n', "\r");
            let result = analyze(source.as_bytes(), &policy(), "x.py");
            let diagnostic = result.diagnostic.unwrap();
            assert_eq!(diagnostic.code, "LMH006");
            assert_eq!(diagnostic.line, 1);
            assert!(!diagnostic.fixable);
            assert!(result.replacement.is_none());
        }
        let mixed = header("2024").replacen('\n', "\r", 1);
        assert!(
            analyze(mixed.as_bytes(), &policy(), "x.py")
                .replacement
                .is_none()
        );
    }

    #[test]
    fn incomplete_token_scans_never_hide_a_later_copyright() {
        for body in ["x = 0xZZ\n", "x = ) )\n", "x = f\"{\n 1 + 1\n}\"\n"] {
            let source = format!("{}{body}", header("2024"));
            // Malformed bodies alone do not prevent an unambiguous year-only repair.
            assert!(
                analyze(source.as_bytes(), &policy(), "x.py")
                    .replacement
                    .is_some()
            );
            for tail in [
                "# Copyright (C) 2024, Other Owner.\n",
                "example = '# Copyright (C) 2024, Other Owner.'\n",
            ] {
                let result = analyze(format!("{source}{tail}").as_bytes(), &policy(), "x.py");
                let diagnostic = result.diagnostic.unwrap();
                assert_eq!(diagnostic.code, "LMH006", "{body}{tail}");
                assert_eq!(diagnostic.line, 1);
                assert!(!diagnostic.fixable);
                assert!(result.replacement.is_none());
            }
        }
    }

    #[test]
    fn expression_comments_inside_formatted_or_template_strings_are_ambiguous() {
        for prefix in ["f", "F", "rf", "fr", "t", "T", "tr", "rt", "tR", "RT"] {
            let source = format!(
                "{}\nx = {prefix}'''{{\n# Copyright (C) 2024, Other Owner.\n1\n}}'''\n",
                header("2024")
            );
            let result = analyze(source.as_bytes(), &policy(), "x.py");
            let diagnostic = result.diagnostic.unwrap();
            assert_eq!(diagnostic.code, "LMH006", "{prefix}");
            assert!(!diagnostic.fixable);
            assert!(result.replacement.is_none());
        }
        let literal = format!(
            "{}\nx = '''{{\n# Copyright (C) 2024, Other Owner.\n1\n}}'''\n",
            header("2024")
        );
        assert!(
            analyze(literal.as_bytes(), &policy(), "x.py")
                .replacement
                .is_some()
        );
    }

    #[test]
    fn literal_formatted_headers_and_escaped_braces_are_not_comments() {
        for value in [
            "# Copyright (C) {year}, Example Owner.",
            "{year}\n# Copyright (C) 2024, Example Owner.",
            "{{\n# Copyright (C) 2024, Example Owner.\n}}",
        ] {
            let source = format!("{}\nx = f'''{value}'''\n", header("2024"));
            assert!(
                analyze(source.as_bytes(), &policy(), "x.py")
                    .replacement
                    .is_some(),
                "{value}"
            );
        }
        for value in [
            "{{{\n# Copyright (C) 2024, Other.\n1\n}}}",
            "{'}}'\n# Copyright (C) 2024, Other.\n}",
            "{\n# closing } brace in comment\n# Copyright (C) 2024, Other.\n1\n}",
        ] {
            assert!(expression_may_contain_copyright(value), "{value}");
        }
        let source = include_str!("../.github/smoke_distribution.py");
        let mut fixture_policy = policy();
        fixture_policy.owner = "François-Guillaume Fernandez".into();
        fixture_policy.current_year = 2026;
        fixture_policy.license_notices = vec![
            "# This program is licensed under the Apache License 2.0.\n\
             # See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.\n".into(),
        ];
        assert!(
            analyze(source.as_bytes(), &fixture_policy, "smoke_distribution.py")
                .diagnostic
                .is_none()
        );
    }
}
