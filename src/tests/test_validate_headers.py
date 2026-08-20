# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

import json
import os
import stat
import sys
import unittest
from contextlib import chdir
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).parents[1]))
import validate_headers

OWNER = "Example Owner"
CURRENT_YEAR = 2030
APACHE_NOTICE = [
    "# This program is licensed under the Apache License 2.0.\n",
    "# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.\n",
]


class ValidateHeadersTestCase(unittest.TestCase):
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
            "folders": "src",
            "ignore_files": "",
            "ignore_folders": "",
            "license_notice": "",
            "mode": "check",
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
        shebang=False,
        body="value = 'café'\n",
        bom=False,
    ):
        source_path = Path(path)
        source_path.parent.mkdir(parents=True, exist_ok=True)
        if years is None:
            source = body
        else:
            header = []
            if shebang:
                header.extend(["#!usr/bin/python\n", "\n"])
            header.extend([f"# Copyright (C) {years}, {owner}.\n", "\n", *notice])
            source = "".join(header) + "\n" + body
        raw_source = source.replace("\n", newline).encode()
        if bom:
            raw_source = b"\xef\xbb\xbf" + raw_source
        source_path.write_bytes(raw_source)
        return source_path

    def test_valid_current_single_and_range(self):
        self.write_source("src/single.py", "2030")
        self.write_source("src/range.py", "2024-2030")

        invalid_files, _ = validate_headers.run(self.make_args(), CURRENT_YEAR)

        self.assertEqual(invalid_files, [])

    def test_fix_stale_single_range_and_second_run_is_idempotent(self):
        single = self.write_source("src/single.py", "2024")
        ranged = self.write_source("src/range.py", "2024-2029")

        invalid_files, _ = validate_headers.run(self.make_args(mode="fix"), CURRENT_YEAR)

        self.assertEqual(invalid_files, [])
        self.assertIn(b"Copyright (C) 2024-2030", single.read_bytes())
        self.assertIn(b"Copyright (C) 2024-2030", ranged.read_bytes())
        first_result = {path: path.read_bytes() for path in (single, ranged)}

        invalid_files, _ = validate_headers.run(self.make_args(mode="fix"), CURRENT_YEAR)

        self.assertEqual(invalid_files, [])
        self.assertEqual(first_result, {path: path.read_bytes() for path in (single, ranged)})

    def test_fix_preserves_shebang_custom_notice_crlf_bom_bytes_and_mode(self):
        custom_notice = Path("notice.txt")
        custom_notice.write_text("# Proprietary.\n# All rights reserved.\n", encoding="utf-8")
        notice = custom_notice.read_text(encoding="utf-8").splitlines(keepends=True)
        shebang = self.write_source(
            "src/shebang.py",
            "2024",
            notice=notice,
            newline="\r\n",
            shebang=True,
            body="value = 'café'\n",
        )
        encoded = self.write_source("src/encoded.py", "2025", notice=notice, bom=True)
        shebang.chmod(0o754)
        original_mode = stat.S_IMODE(shebang.stat().st_mode)
        expected_shebang = shebang.read_bytes().replace(b"Copyright (C) 2024", b"Copyright (C) 2024-2030", 1)
        expected_encoded = encoded.read_bytes().replace(b"Copyright (C) 2025", b"Copyright (C) 2025-2030", 1)

        invalid_files, _ = validate_headers.run(
            self.make_args(mode="fix", license="", license_notice=str(custom_notice)),
            CURRENT_YEAR,
        )

        self.assertEqual(invalid_files, [])
        self.assertEqual(shebang.read_bytes(), expected_shebang)
        self.assertEqual(encoded.read_bytes(), expected_encoded)
        self.assertEqual(stat.S_IMODE(shebang.stat().st_mode), original_mode)

    def test_discovery_handles_ignores_and_multiple_folders(self):
        first = self.write_source("src/a.py")
        second = self.write_source("other/b.py")
        self.write_source("src/ignored.py", None)
        self.write_source("src/skip/bad.py", None)

        source_paths = validate_headers.discover_files("src,other", "ignored.py", "src/skip")
        invalid_files, _ = validate_headers.run(
            self.make_args(
                folders="src,other",
                ignore_files="ignored.py",
                ignore_folders="src/skip",
            ),
            CURRENT_YEAR,
        )

        self.assertEqual(source_paths, [first, second])
        self.assertEqual(invalid_files, [])

    def test_fix_repairs_safe_files_but_leaves_ambiguous_files_unchanged(self):
        safe = self.write_source("src/safe.py", "2024")
        invalid_paths = {
            self.write_source("src/missing.py", None),
            self.write_source("src/owner.py", "2024", owner="Another Owner"),
            self.write_source("src/malformed.py", "20x4"),
            self.write_source("src/future.py", "2031"),
            self.write_source("src/reversed.py", "2029-2028"),
            self.write_source(
                "src/license.py",
                "2024",
                notice=["# Unknown license.\n", "# No recognized license text.\n"],
            ),
        }
        original_bytes = {path: path.read_bytes() for path in invalid_paths}

        invalid_files, _ = validate_headers.run(self.make_args(mode="fix"), CURRENT_YEAR)

        self.assertIn(b"Copyright (C) 2024-2030", safe.read_bytes())
        self.assertEqual(set(invalid_files), invalid_paths)
        self.assertEqual(original_bytes, {path: path.read_bytes() for path in invalid_paths})

    def test_check_mode_never_writes_sources(self):
        source_path = self.write_source("src/stale.py", "2024")
        original_bytes = source_path.read_bytes()
        original_stat = source_path.stat()

        invalid_files, _ = validate_headers.run(self.make_args(), CURRENT_YEAR)

        self.assertEqual(invalid_files, [source_path])
        self.assertEqual(source_path.read_bytes(), original_bytes)
        self.assertEqual(source_path.stat().st_mtime_ns, original_stat.st_mtime_ns)

    def test_invalid_mode_and_configuration_fail(self):
        Path("src").mkdir()
        invalid_args = [
            self.make_args(mode="rewrite"),
            self.make_args(owner=""),
            self.make_args(year=2031),
            self.make_args(folders="missing"),
            self.make_args(license="unknown"),
            self.make_args(license="", license_notice="missing.txt"),
        ]

        for args in invalid_args:
            with self.subTest(args=args), self.assertRaises((FileNotFoundError, ValueError)):
                validate_headers.run(args, CURRENT_YEAR)

    def test_json_issues_output(self):
        output_path = Path("github-output.txt")
        invalid_files = [Path("src/bad.py"), Path(".github/helper.py")]

        with mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_path)}):
            validate_headers.write_issues(invalid_files)

        key, value = output_path.read_text(encoding="utf-8").strip().split("=", 1)
        self.assertEqual(key, "issues")
        self.assertEqual(json.loads(value), ["src/bad.py", ".github/helper.py"])


if __name__ == "__main__":
    unittest.main()
