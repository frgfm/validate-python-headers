# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

import unittest
from contextlib import chdir
from pathlib import Path

from support import WorkspaceTestCase

from validate_headers import cli


class ConfigTestCase(WorkspaceTestCase):
    def test_nearest_configuration_and_cli_precedence(self):
        Path("pyproject.toml").write_text(
            """[tool.validate-python-headers]
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
            configured = cli.resolve_args(cli.parse_args(["check"]))
            overridden = cli.resolve_args(
                cli.parse_args([
                    "fix",
                    "--owner",
                    "CLI Owner",
                    "--starting-year",
                    "2024",
                    "--license-notice",
                    "../notice.txt",
                    "--ignore-files",
                    "one.py,two.py",
                    "selected.py",
                ])
            )

        self.assertEqual(configured.owner, "Config Owner")
        self.assertEqual(configured.year, 2023)
        self.assertEqual(configured.paths, ("../src", "../tests"))
        self.assertEqual(configured.ignore_files, ("generated.py",))
        self.assertEqual(configured.ignore_folders, ())
        self.assertEqual(configured.project_root, self.root)
        self.assertEqual(configured.config_path, self.root / "pyproject.toml")
        self.assertEqual(overridden.owner, "CLI Owner")
        self.assertEqual(overridden.year, 2024)
        self.assertIsNone(overridden.license)
        self.assertEqual(overridden.license_notice, "../notice.txt")
        self.assertEqual(overridden.paths, ("selected.py",))
        self.assertEqual(overridden.ignore_files, ("one.py", "two.py"))

    def test_custom_notice_is_relative_to_pyproject(self):
        Path("notice.txt").write_text("# Proprietary.\n", encoding="utf-8")
        Path("pyproject.toml").write_text(
            """[tool.validate-python-headers]
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
            settings = cli.resolve_args(cli.parse_args(["check"]))

        self.assertEqual(settings.license_notice, "../notice.txt")
        self.assertEqual(settings.license_path, self.root / "LICENSE")

    def test_configuration_errors_name_the_exact_key(self):
        invalid_documents = {
            "missing-owner": """[tool.validate-python-headers]
starting-year = 2022
license = "Apache-2.0"
""",
            "unknown-key": """[tool.validate-python-headers]
owner = "Example Owner"
starting-year = 2022
license = "Apache-2.0"
wat = true
""",
            "bad-paths": """[tool.validate-python-headers]
owner = "Example Owner"
starting-year = 2022
license = "Apache-2.0"
paths = []
""",
            "two-licenses": """[tool.validate-python-headers]
owner = "Example Owner"
starting-year = 2022
license = "Apache-2.0"
license-notice = "notice.txt"
""",
        }
        expected = {
            "missing-owner": "[tool.validate-python-headers].owner",
            "unknown-key": "[tool.validate-python-headers].wat",
            "bad-paths": "[tool.validate-python-headers].paths",
            "two-licenses": "Configure exactly one",
        }

        for name, document in invalid_documents.items():
            with self.subTest(name=name):
                Path("pyproject.toml").write_text(document, encoding="utf-8")
                with self.assertRaises((ValueError, FileNotFoundError)) as raised:
                    cli.resolve_args(cli.parse_args(["check"]))
                self.assertIn(expected[name], str(raised.exception))

    def test_explicit_paths_and_legacy_folders_are_mutually_exclusive(self):
        args = cli.parse_args([
            "check",
            "--owner",
            "Example Owner",
            "--starting-year",
            "2022",
            "--license",
            "Apache-2.0",
            "--folders",
            "src",
            "selected.py",
        ])

        with self.assertRaisesRegex(ValueError, "explicit paths"):
            cli.resolve_args(args)


if __name__ == "__main__":
    unittest.main()
