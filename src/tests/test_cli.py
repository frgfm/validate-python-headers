# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

import io
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from support import CURRENT_YEAR, OWNER, WorkspaceTestCase

from validate_headers import cli


class CliTestCase(WorkspaceTestCase):
    def common_args(self):
        return [
            "--owner",
            OWNER,
            "--starting-year",
            "2022",
            "--license",
            "Apache-2.0",
            "--ignore-files",
            "",
            "--ignore-folders",
            "",
        ]

    def test_json_finding_is_stdout_only_and_schema_stable(self):
        self.write_source("src/b.py", None)
        self.write_source("src/a.py", "2024")

        exit_code, stdout, stderr = self.capture_main(["check", *self.common_args(), "--output-format", "json", "src"])
        payload = json.loads(stdout)

        self.assertEqual(exit_code, 1)
        self.assertEqual(stderr, "")
        self.assertEqual(
            list(payload),
            [
                "schema_version",
                "tool_version",
                "command",
                "config_path",
                "checked",
                "changed",
                "diagnostics",
                "expected_header",
                "error",
            ],
        )
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["command"], "check")
        self.assertEqual(payload["changed"], [])
        self.assertEqual([item["path"] for item in payload["diagnostics"]], ["src/a.py", "src/b.py"])
        self.assertEqual([item["code"] for item in payload["diagnostics"]], ["VPH004", "VPH001"])
        self.assertIsNone(payload["error"])

    def test_json_fix_reports_changed_and_only_unresolved_findings(self):
        self.write_source("src/stale.py", "2024")
        self.write_source("src/missing.py", None)

        with mock.patch("validate_headers.core.datetime") as current_datetime:
            current_datetime.now.return_value.year = CURRENT_YEAR
            exit_code, stdout, stderr = self.capture_main([
                "fix",
                *self.common_args(),
                "--output-format",
                "json",
                "src",
            ])
        payload = json.loads(stdout)

        self.assertEqual(exit_code, 1)
        self.assertEqual(stderr, "")
        self.assertEqual(payload["changed"], ["src/stale.py"])
        self.assertEqual([item["path"] for item in payload["diagnostics"]], ["src/missing.py"])

    def test_json_error_envelope_and_action_outputs(self):
        output_path = Path("github-output.txt")

        exit_code, stdout, stderr = self.capture_main(
            ["check", *self.common_args(), "--output-format", "json", "missing.py"],
            github_output=output_path,
        )
        payload = json.loads(stdout)

        self.assertEqual(exit_code, 2)
        self.assertEqual(stderr, "")
        self.assertEqual(payload["checked"], 0)
        self.assertEqual(payload["changed"], [])
        self.assertEqual(payload["diagnostics"], [])
        self.assertIsNotNone(payload["expected_header"])
        self.assertEqual(payload["error"]["code"], "VPH900")
        self.assertIn("Invalid path", payload["error"]["message"])
        self.assertEqual(output_path.read_text(encoding="utf-8"), "issues=[]\nchanged=[]\n")

    def test_text_output_is_compiler_style(self):
        self.write_source("src/stale.py", "2024")

        with mock.patch("validate_headers.core.datetime") as current_datetime:
            current_datetime.now.return_value.year = CURRENT_YEAR
            exit_code, stdout, stderr = self.capture_main(["check", *self.common_args(), "src/stale.py"])

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("src/stale.py:1:1: VPH004", stderr)
        self.assertIn("[fixable]", stderr)
        self.assertIn("Expected header:", stderr)

    def test_action_outputs_preserve_issues_and_add_changed(self):
        output_path = Path("github-output.txt")
        self.write_source("src/stale.py", "2024")
        self.write_source("src/missing.py", None)

        with mock.patch("validate_headers.core.datetime") as current_datetime:
            current_datetime.now.return_value.year = CURRENT_YEAR
            exit_code, _, _ = self.capture_main(
                ["fix", *self.common_args(), "src"],
                github_output=output_path,
            )

        self.assertEqual(exit_code, 1)
        self.assertEqual(
            output_path.read_text(encoding="utf-8"),
            'issues=["src/missing.py"]\nchanged=["src/stale.py"]\n',
        )

    def test_version_uses_distribution_metadata(self):
        stdout = io.StringIO()
        with (
            mock.patch("validate_headers.cli.version", return_value="0.6.0rc1"),
            mock.patch("sys.stdout", stdout),
            self.assertRaises(SystemExit) as raised,
        ):
            cli.parse_args(["--version"])

        self.assertEqual(raised.exception.code, 0)
        self.assertTrue(stdout.getvalue().endswith(" 0.6.0rc1\n"))

    def test_legacy_write_issues_stays_compact(self):
        output_path = Path("github-output.txt")
        with mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_path)}):
            cli.write_issues([Path("src/bad.py"), Path(".github/helper.py")])
        self.assertEqual(
            output_path.read_text(encoding="utf-8"),
            'issues=["src/bad.py",".github/helper.py"]\n',
        )


if __name__ == "__main__":
    unittest.main()
