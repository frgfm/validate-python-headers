# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

import io
import json
import os
import stat
import subprocess
import sys
import unittest
from contextlib import chdir, redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

REPOSITORY_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(Path(__file__).parents[1]))
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

from lint_my_headers import cli
from lint_my_headers import config
from lint_my_headers import core
import pypi_files  # ty: ignore[unresolved-import]
from release_version import release_version  # ty: ignore[unresolved-import]

OWNER = "Example Owner"
CURRENT_YEAR = 2030
APACHE_NOTICE = (
    "# This program is licensed under the Apache License 2.0.",
    "# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.",
)


class LintMyHeadersTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.change_directory = chdir(self.temporary_directory.name)
        self.change_directory.__enter__()
        Path("LICENSE").write_text("Apache-2.0\n", encoding="utf-8")

    def tearDown(self):
        self.change_directory.__exit__(None, None, None)
        self.temporary_directory.cleanup()

    def make_args(self, **overrides):
        values = {
            "owner": OWNER,
            "year": 2022,
            "license": "Apache-2.0",
            "paths": ["src"],
            "ignore_files": [],
            "ignore_folders": [],
            "license_notice": None,
            "license_path": Path("LICENSE"),
            "mode": "check",
            "project_root": Path.cwd(),
            "config_display": None,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def write_source(
        self,
        path,
        years="2030",
        *,
        owner=OWNER,
        notice=APACHE_NOTICE,
        newline="\n",
        preamble=(),
        body="value = 'café'\n",
        encoding="utf-8",
        bom=False,
    ):
        source_path = Path(path)
        source_path.parent.mkdir(parents=True, exist_ok=True)
        if years is None:
            source = "\n".join(preamble) + ("\n" if preamble else "") + body
        else:
            header = [*preamble, f"# Copyright (C) {years}, {owner}.", "", *notice]
            source = "\n".join(header) + "\n\n" + body
        raw_source = source.replace("\n", newline).encode(encoding)
        if bom:
            raw_source = b"\xef\xbb\xbf" + raw_source
        source_path.write_bytes(raw_source)
        return source_path

    def execute(self, **overrides):
        return core.run(self.make_args(**overrides), CURRENT_YEAR)

    def test_every_primary_diagnostic_and_precedence(self):
        self.write_source("src/missing.py", None)
        self.write_source("src/owner.py", owner="Another Owner")
        self.write_source("src/year.py", "2031")
        self.write_source("src/stale.py", "2029")
        self.write_source("src/license.py", notice=("# Unknown license.",))
        self.write_source("src/layout.py", "20x4")
        Path("src/encoding.py").write_bytes(b"# coding: unknown-codec\n")
        duplicated = self.write_source("src/duplicate.py")
        duplicated.write_bytes(
            duplicated.read_bytes().replace(b"\n\nvalue", b"\n# Copyright (C) 2030, Example Owner.\n\nvalue")
        )

        result = self.execute()

        self.assertEqual([item.path for item in result.diagnostics], sorted(item.path for item in result.diagnostics))
        codes = {diagnostic.path: diagnostic.code for diagnostic in result.diagnostics}
        self.assertEqual(
            codes,
            {
                "src/duplicate.py": "LMH006",
                "src/encoding.py": "LMH007",
                "src/layout.py": "LMH006",
                "src/license.py": "LMH005",
                "src/missing.py": "LMH001",
                "src/owner.py": "LMH002",
                "src/stale.py": "LMH004",
                "src/year.py": "LMH003",
            },
        )
        stale = next(diagnostic for diagnostic in result.diagnostics if diagnostic.code == "LMH004")
        self.assertTrue(stale.fixable)
        self.assertEqual(result.exit_code, 1)

        wrong_owner_and_license = self.write_source(
            "selected.py",
            owner="Wrong Owner",
            notice=("# Wrong license.",),
        )
        selected = self.execute(paths=[str(wrong_owner_and_license)])
        self.assertEqual([diagnostic.code for diagnostic in selected.diagnostics], ["LMH002"])

        preamble_owner = self.write_source(
            "preamble-owner.py",
            owner="Wrong Owner",
            preamble=("#!/usr/bin/env python3", ""),
        )
        preamble_result = self.execute(paths=[str(preamble_owner)])
        self.assertEqual((preamble_result.diagnostics[0].line, preamble_result.diagnostics[0].column), (3, 1))

    def test_python_preambles_bom_and_newlines(self):
        self.write_source("src/shebang.py", preamble=("#!/usr/bin/env -S python -O", ""))
        self.write_source("src/cookie.py", preamble=("# coding: latin-1", ""), encoding="latin-1")
        self.write_source(
            "src/both.py",
            preamble=("#!/usr/bin/python3", "# -*- coding: utf-8 -*-", ""),
            newline="\r\n",
        )
        self.write_source("src/bom.py", newline="\r\n", bom=True)

        result = self.execute()

        self.assertEqual(result.diagnostics, [])
        conflict = Path("conflict.py")
        conflict.write_bytes(b"\xef\xbb\xbf# coding: latin-1\n")
        invalid = self.execute(paths=[str(conflict)])
        self.assertEqual(invalid.diagnostics[0].code, "LMH007")

    def test_fix_is_atomic_byte_preserving_and_idempotent(self):
        source = self.write_source(
            "src/stale.py",
            "2024",
            preamble=("#!/usr/bin/env python3", "# coding: utf-8", ""),
            newline="\r\n",
            bom=True,
        )
        source.chmod(0o754)
        original = source.read_bytes()
        expected = original.replace(b"Copyright (C) 2024", b"Copyright (C) 2024-2030", 1)
        mode = stat.S_IMODE(source.stat().st_mode)

        result = self.execute(mode="fix")

        self.assertEqual(result.changed, ["src/stale.py"])
        self.assertEqual(result.diagnostics, [])
        self.assertEqual(source.read_bytes(), expected)
        self.assertEqual(stat.S_IMODE(source.stat().st_mode), mode)
        second = self.execute(mode="fix")
        self.assertEqual(second.changed, [])
        self.assertEqual(source.read_bytes(), expected)

    def test_check_never_writes_and_fix_leaves_ambiguous_files(self):
        stale = self.write_source("src/stale.py", "2024")
        ambiguous = self.write_source("src/ambiguous.py", "20x4")
        originals = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in (stale, ambiguous)}

        check_result = self.execute()

        self.assertEqual(check_result.changed, [])
        self.assertEqual({path: (path.read_bytes(), path.stat().st_mtime_ns) for path in originals}, originals)
        fix_result = self.execute(mode="fix")
        self.assertEqual(fix_result.changed, ["src/stale.py"])
        self.assertEqual([(item.path, item.code) for item in fix_result.diagnostics], [("src/ambiguous.py", "LMH006")])
        self.assertEqual(ambiguous.read_bytes(), originals[ambiguous][0])

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_symlink_files_are_visible_but_never_repaired(self):
        target = self.write_source("target/stale.py", "2024")
        Path("src").mkdir()
        link = Path("src/link.py")
        try:
            link.symlink_to(target.absolute())
        except OSError as error:
            self.skipTest(f"symlink creation is unavailable: {error}")
        original = target.read_bytes()

        check_result = self.execute(paths=[str(link)])
        fix_result = self.execute(paths=[str(link)], mode="fix")

        self.assertEqual(check_result.diagnostics[0].code, "LMH004")
        self.assertFalse(check_result.diagnostics[0].fixable)
        self.assertEqual(fix_result.diagnostics[0].code, "LMH008")
        self.assertEqual(target.read_bytes(), original)

        discovered = self.execute(paths=["src"])
        self.assertEqual(discovered.checked, 0)

        directory_link = Path("linked-directory")
        try:
            directory_link.symlink_to(Path("target").absolute(), target_is_directory=True)
        except OSError as error:
            self.skipTest(f"directory symlink creation is unavailable: {error}")
        with self.assertRaisesRegex(ValueError, "symlink or reparse"):
            core.discover_files([str(directory_link)], [], [])
        through_parent = self.execute(paths=[str(directory_link / "stale.py")], mode="fix")
        self.assertEqual(through_parent.diagnostics[0].code, "LMH008")
        self.assertEqual(target.read_bytes(), original)

    @unittest.skipUnless(hasattr(os, "link"), "hard links are unavailable")
    def test_multi_link_files_are_never_repaired(self):
        source = self.write_source("src/stale.py", "2024")
        alias = Path("src/alias.py")
        os.link(source, alias)
        original = source.read_bytes()

        check_result = self.execute(paths=[str(source)])
        fix_result = self.execute(paths=[str(source)], mode="fix")

        self.assertEqual(check_result.diagnostics[0].code, "LMH004")
        self.assertFalse(check_result.diagnostics[0].fixable)
        self.assertEqual(fix_result.diagnostics[0].code, "LMH008")
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(alias.read_bytes(), original)

    def test_changed_file_race_fails_closed(self):
        source = self.write_source("src/stale.py", "2024")
        original = source.read_bytes()

        with mock.patch.object(core, "_identity_matches", side_effect=[True, False]):
            result = self.execute(mode="fix")

        self.assertEqual(result.diagnostics[0].code, "LMH008")
        self.assertEqual(result.changed, [])
        self.assertEqual(source.read_bytes(), original)

    def test_discovery_ignores_symlinks_and_lexical_duplicates(self):
        first = self.write_source("src/a.py")
        second = self.write_source("src/b.py")
        self.write_source("src/generated.py", None)
        self.write_source("src/vendor/bad.py", None)

        paths = core.discover_files([str(first), "src", "src/../src/a.py"], ["generated.py"], ["src/vendor"])

        self.assertEqual(paths, [first, second])
        with self.assertRaisesRegex(FileNotFoundError, "Invalid path"):
            core.discover_files(["missing.py"], [], [])

    def test_explicit_external_paths_are_project_relative_posix_paths(self):
        project_root = Path("project")
        project_root.mkdir()
        outside = self.write_source("outside.py", None)

        result = self.execute(paths=[str(outside)], project_root=project_root)

        self.assertEqual(result.diagnostics[0].path, "../outside.py")

    def test_configuration_root_defaults_and_cli_precedence(self):
        Path("pyproject.toml").write_text(
            """[tool.lint-my-headers]
owner = "Config Owner"
starting-year = 2023
license = "Apache-2.0"
paths = ["src", "tests"]
ignore-files = ["generated.py"]
ignore-folders = []
""",
            encoding="utf-8",
        )
        Path("nested").mkdir()

        with chdir("nested"):
            args = config.resolve_args(cli.parse_args(["check"]))

        self.assertEqual(args.owner, "Config Owner")
        self.assertEqual(args.year, 2023)
        self.assertEqual(args.paths, ["../src", "../tests"])
        self.assertEqual(args.config_display, "pyproject.toml")

        overridden = config.resolve_args(
            cli.parse_args([
                "fix",
                "--owner",
                "CLI Owner",
                "--starting-year",
                "2024",
                "--license-notice",
                "notice.txt",
                "--ignore-files",
                "one.py,two.py",
                "selected.py",
            ])
        )
        self.assertEqual(overridden.owner, "CLI Owner")
        self.assertEqual(overridden.year, 2024)
        self.assertIsNone(overridden.license)
        self.assertEqual(overridden.paths, ["selected.py"])
        self.assertEqual(overridden.ignore_files, ["one.py", "two.py"])

    def test_configuration_is_strict_and_old_table_is_not_an_alias(self):
        Path("pyproject.toml").write_text(
            """[tool.lint-my-headers]
owner = "Example Owner"
starting-year = 2022
license = "Apache-2.0"
paths = "src"
""",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, r"\[tool\.lint-my-headers\]\.paths"):
            config.resolve_args(cli.parse_args(["check"]))

        Path("pyproject.toml").write_text(
            """[tool.validate-python-headers]
owner = "Example Owner"
starting-year = 2022
license = "Apache-2.0"
""",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, r"\[tool\.lint-my-headers\]\.owner"):
            config.resolve_args(cli.parse_args(["check"]))

    def test_custom_notice_is_relative_to_configuration(self):
        Path("notice.txt").write_text("# Proprietary.\n# All rights reserved.\n", encoding="utf-8")
        notice = ("# Proprietary.", "# All rights reserved.")
        self.write_source("src/custom.py", notice=notice)
        Path("pyproject.toml").write_text(
            """[tool.lint-my-headers]
owner = "Example Owner"
starting-year = 2022
license-notice = "notice.txt"
paths = ["src"]
ignore-files = []
ignore-folders = []
""",
            encoding="utf-8",
        )
        Path("nested").mkdir()

        with chdir("nested"):
            args = config.resolve_args(cli.parse_args(["check"]))
            result = core.run(args, CURRENT_YEAR)

        self.assertEqual(result.diagnostics, [])

    def test_json_contract_for_clean_findings_and_errors(self):
        current = str(datetime.now().year)
        valid = self.write_source("valid.py", current)
        invalid = self.write_source("invalid.py", None)
        common = [
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
            "--output-format",
            "json",
        ]

        for path, expected_code, expected_exit in ((valid, None, 0), (invalid, "LMH001", 1)):
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                return_code = cli.main(["check", *common, str(path)])
            payload = json.loads(stdout.getvalue())
            self.assertEqual(return_code, expected_exit)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["command"], "check")
            self.assertEqual(payload["checked"], 1)
            self.assertEqual(payload["changed"], [])
            self.assertEqual(payload["error"], None)
            self.assertEqual(
                set(payload),
                {
                    "schema_version",
                    "tool_version",
                    "command",
                    "config_path",
                    "checked",
                    "changed",
                    "diagnostics",
                    "expected_header",
                    "error",
                },
            )
            self.assertEqual(
                [item["code"] for item in payload["diagnostics"]], [] if expected_code is None else [expected_code]
            )
            if expected_code is not None:
                self.assertEqual(
                    payload["diagnostics"],
                    [
                        {
                            "code": "LMH001",
                            "column": 1,
                            "fixable": False,
                            "line": 1,
                            "message": "legal header is missing",
                            "path": "invalid.py",
                        }
                    ],
                )

        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            return_code = cli.main(["check", *common, "missing.py"])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(return_code, 2)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(payload["checked"], 0)
        self.assertEqual(payload["error"], {"code": "LMH900", "message": "Invalid path: missing.py", "path": None})
        self.assertEqual(payload["diagnostics"], [])
        self.assertIsNotNone(payload["expected_header"])

        invalid_policy = ["Not-A-License" if item == "Apache-2.0" else item for item in common]
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            return_code = cli.main(["check", *invalid_policy, str(valid)])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(return_code, 2)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(payload["error"]["code"], "LMH900")
        self.assertIsNone(payload["expected_header"])

    def test_text_contract_version_and_action_outputs(self):
        invalid = self.write_source("invalid.py", None)
        common = [
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
        stderr = io.StringIO()
        output_path = Path("github-output.txt")

        with mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_path)}), redirect_stderr(stderr):
            return_code = cli.main(["check", *common, str(invalid)])

        self.assertEqual(return_code, 1)
        self.assertIn("invalid.py:1:1: LMH001", stderr.getvalue())
        outputs = dict(line.split("=", 1) for line in output_path.read_text(encoding="utf-8").splitlines())
        self.assertEqual(json.loads(outputs["issues"]), ["invalid.py"])
        self.assertEqual(json.loads(outputs["changed"]), [])
        self.assertEqual(cli.tool_version(), "0.6.0rc1")

    def test_release_tag_must_exactly_match_package_version(self):
        pyproject = REPOSITORY_ROOT / "pyproject.toml"

        self.assertEqual(release_version("v0.6.0rc1", pyproject), "0.6.0rc1")
        with self.assertRaisesRegex(ValueError, "does not match"):
            release_version("v0.6.0", pyproject)
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            release_version("release-0.6.0rc1", pyproject)

    def test_pypi_retry_selection_skips_only_identical_files(self):
        wheel = Path("lint_my_headers-0.6.0rc1-py3-none-any.whl")
        source = Path("lint_my_headers-0.6.0rc1.tar.gz")
        wheel.write_bytes(b"wheel")
        source.write_bytes(b"source")

        with mock.patch.object(pypi_files, "_remote_files", return_value={wheel.name: pypi_files._digest(wheel)}):
            self.assertEqual(pypi_files._compare("0.6.0rc1", [wheel, source]), [source])
        with (
            mock.patch.object(pypi_files, "_remote_files", return_value={wheel.name: "0" * 64}),
            self.assertRaisesRegex(RuntimeError, "hash mismatch"),
        ):
            pypi_files._compare("0.6.0rc1", [wheel])

    def test_action_changed_output_contains_completed_writes(self):
        stale = self.write_source("src/stale.py", "2024")
        bad = self.write_source("src/bad.py", None)
        result = self.execute(mode="fix")
        output_path = Path("github-output.txt")

        with mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_path)}):
            cli.write_action_outputs(result)

        outputs = dict(line.split("=", 1) for line in output_path.read_text(encoding="utf-8").splitlines())
        self.assertEqual(json.loads(outputs["changed"]), ["src/stale.py"])
        self.assertEqual(json.loads(outputs["issues"]), ["src/bad.py"])
        self.assertIn(b"2024-2030", stale.read_bytes())
        self.assertNotIn(b"Copyright", bad.read_bytes())

    def test_scan_error_retains_completed_changes_and_action_outputs(self):
        bad = self.write_source("src/a-bad.py", None)
        stale = self.write_source("src/b-stale.py", "2024")
        self.write_source("src/z.py")
        original_read_bytes = Path.read_bytes

        def read_bytes(path):
            if path.name == "z.py":
                raise OSError("simulated read failure")
            return original_read_bytes(path)

        with mock.patch.object(Path, "read_bytes", read_bytes):
            result = self.execute(mode="fix")

        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.changed, ["src/b-stale.py"])
        self.assertEqual([(item.path, item.code) for item in result.diagnostics], [("src/a-bad.py", "LMH001")])
        self.assertEqual(result.error.code, "LMH900")
        self.assertEqual(result.error.path, "src/z.py")
        self.assertIn(b"2024-2030", stale.read_bytes())

        stderr = io.StringIO()
        with redirect_stderr(stderr):
            cli._render_text(result)
        self.assertIn("error: src/z.py: simulated read failure", stderr.getvalue())
        self.assertIn("src/a-bad.py:1:1: LMH001", stderr.getvalue())

        output_path = Path("github-output.txt")
        with mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_path)}):
            cli.write_action_outputs(result)
        outputs = dict(line.split("=", 1) for line in output_path.read_text(encoding="utf-8").splitlines())
        self.assertEqual(json.loads(outputs["changed"]), ["src/b-stale.py"])
        self.assertEqual(json.loads(outputs["issues"]), [])
        self.assertNotIn(b"Copyright", bad.read_bytes())

    def test_spdx_snapshot_additions_and_all_legacy_notices(self):
        baseline = subprocess.run(
            ["git", "show", "94972478:src/validate_headers/supported-licenses.json"],
            cwd=REPOSITORY_ROOT,
            check=True,
            stdout=subprocess.PIPE,
        ).stdout
        old_items = {item["licenseId"]: item for item in json.loads(baseline)["licenses"]}
        self.assertEqual(len(core.LICENSES), 727)
        self.assertGreater(len(set(core.LICENSES) - set(old_items)), 0)

        for identifier, item in old_items.items():
            with self.subTest(identifier=identifier):
                policy = core.build_policy(OWNER, 2022, identifier, None, current_year=CURRENT_YEAR)
                for url in item["seeAlso"]:
                    expected = (
                        f"# This program is licensed under the {item['name']}.",
                        f"# See LICENSE or go to <{url}> for full license details.",
                    )
                    self.assertIn(expected, policy.notices)


if __name__ == "__main__":
    unittest.main()
