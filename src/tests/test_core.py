# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

import os
import stat
import unittest
from pathlib import Path
from unittest import mock

from support import CURRENT_YEAR, WorkspaceTestCase

from validate_headers import core


class CoreTestCase(WorkspaceTestCase):
    def test_valid_headers_and_python_preambles(self):
        self.write_source("src/single.py", "2030")
        self.write_source("src/range.py", "2024-2030")
        self.write_source("src/shebang.py", preamble=("#!/usr/bin/env python3\n",))
        self.write_source("src/cookie.py", preamble=("# coding: utf-8\n",))
        self.write_source(
            "src/shebang_cookie.py",
            preamble=("#!/opt/project/python\n", "# -*- coding: utf-8 -*-\n"),
        )
        self.write_source("src/bom_crlf.py", preamble=("# coding=utf-8\n",), newline="\r\n", bom=True)

        result = core.run(self.settings(), "check", CURRENT_YEAR)

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.checked, 6)
        self.assertEqual(result.diagnostics, ())
        settings = self.settings()
        options = core.get_header_options(
            settings.owner,
            settings.year,
            settings.license,
            settings.license_notice,
            CURRENT_YEAR,
            settings.license_path,
        )
        for name in ("single.py", "shebang.py", "cookie.py", "shebang_cookie.py", "bom_crlf.py"):
            self.assertTrue(core.is_valid_header(Path("src", name).read_bytes(), options))

    def test_each_invalid_file_has_one_primary_diagnostic(self):
        self.write_source("src/missing.py", None)
        self.write_source("src/owner.py", owner="Another Owner")
        self.write_source("src/future.py", "2031")
        self.write_source("src/stale.py", "2024")
        self.write_source("src/license.py", notice="# Wrong license notice.\n")
        self.write_source("src/layout.py", "20x4")
        Path("src/decode.py").write_bytes(b"# coding: made-up-codec\nvalue = 1\n")

        result = core.run(self.settings(), "check", CURRENT_YEAR)
        diagnostics = {item.path.name: item for item in result.diagnostics}

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(len(diagnostics), 7)
        self.assertEqual(diagnostics["missing.py"].code, core.DiagnosticCode.MISSING_HEADER)
        self.assertEqual(diagnostics["owner.py"].code, core.DiagnosticCode.OWNER_MISMATCH)
        self.assertEqual(diagnostics["future.py"].code, core.DiagnosticCode.INVALID_YEAR)
        self.assertEqual(diagnostics["stale.py"].code, core.DiagnosticCode.STALE_YEAR)
        self.assertTrue(diagnostics["stale.py"].fixable)
        self.assertEqual(diagnostics["license.py"].code, core.DiagnosticCode.LICENSE_MISMATCH)
        self.assertEqual(diagnostics["layout.py"].code, core.DiagnosticCode.INVALID_LAYOUT)
        self.assertEqual(diagnostics["decode.py"].code, core.DiagnosticCode.DECODE_ERROR)

    def test_second_line_cookie_after_code_is_not_a_python_preamble(self):
        path = Path("src/late_cookie.py")
        path.parent.mkdir(parents=True)
        path.write_text(
            """value = 0
# coding: utf-8

# Copyright (C) 2030, Example Owner.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.
""",
            encoding="utf-8",
        )

        result = core.run(self.settings(), "check", CURRENT_YEAR)

        self.assertEqual(result.diagnostics[0].code, core.DiagnosticCode.INVALID_LAYOUT)

    def test_copyright_example_inside_string_is_not_a_duplicate_header(self):
        self.write_source(
            "src/example_string.py",
            body='EXAMPLE = """\n# Copyright (C) 2026, Someone Else.\n"""\n',
        )

        result = core.run(self.settings(), "check", CURRENT_YEAR)

        self.assertEqual(result.exit_code, 0)

    def test_check_never_writes_sources(self):
        path = self.write_source("src/stale.py", "2024")
        original = path.read_bytes()
        original_stat = path.stat()

        result = core.run(self.settings(), "check", CURRENT_YEAR)

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(path.stat().st_mtime_ns, original_stat.st_mtime_ns)

    def test_fix_preserves_preamble_bytes_newlines_mode_and_is_idempotent(self):
        notice_path = Path("notice.txt")
        notice_path.write_text("# Proprietary.\n# All rights reserved.\n", encoding="utf-8")
        notice = notice_path.read_text(encoding="utf-8")
        path = self.write_source(
            "src/stale.py",
            "2024",
            notice=notice,
            preamble=("#!/usr/bin/env python3\n", "# coding: utf-8\n"),
            newline="\r\n",
            bom=True,
        )
        path.chmod(0o754)
        original_mode = stat.S_IMODE(path.stat().st_mode)
        expected = path.read_bytes().replace(b"Copyright (C) 2024", b"Copyright (C) 2024-2030", 1)
        settings = self.settings(license=None, license_notice=str(notice_path))

        first = core.run(settings, "fix", CURRENT_YEAR)
        first_bytes = path.read_bytes()
        second = core.run(settings, "fix", CURRENT_YEAR)

        self.assertEqual(first.exit_code, 0)
        self.assertEqual(first.changed, (path,))
        self.assertEqual(first_bytes, expected)
        self.assertEqual(second.changed, ())
        self.assertEqual(path.read_bytes(), first_bytes)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), original_mode)

    def test_fix_repairs_only_recognized_stale_years(self):
        safe = self.write_source("src/safe.py", "2024")
        invalid = {
            self.write_source("src/missing.py", None),
            self.write_source("src/owner.py", "2024", owner="Another Owner"),
            self.write_source("src/malformed.py", "20x4"),
            self.write_source("src/future.py", "2031"),
            self.write_source("src/reversed.py", "2029-2028"),
        }
        originals = {path: path.read_bytes() for path in invalid}

        result = core.run(self.settings(), "fix", CURRENT_YEAR)

        self.assertEqual(result.changed, (safe,))
        self.assertIn(b"Copyright (C) 2024-2030", safe.read_bytes())
        self.assertEqual({item.path for item in result.diagnostics}, invalid)
        self.assertEqual(originals, {path: path.read_bytes() for path in invalid})

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_fix_refuses_symlink_and_preserves_target(self):
        target = self.write_source("target.py", "2024")
        Path("src").mkdir()
        link = Path("src/link.py")
        try:
            link.symlink_to(target.absolute())
        except OSError as error:
            self.skipTest(str(error))
        original = target.read_bytes()
        settings = self.settings(paths=(str(link),))

        check = core.run(settings, "check", CURRENT_YEAR)
        fixed = core.run(settings, "fix", CURRENT_YEAR)

        self.assertEqual(check.diagnostics[0].code, core.DiagnosticCode.STALE_YEAR)
        self.assertFalse(check.diagnostics[0].fixable)
        self.assertEqual(fixed.diagnostics[0].code, core.DiagnosticCode.UNSAFE_FIX)
        self.assertTrue(link.is_symlink())
        self.assertEqual(target.read_bytes(), original)

    @unittest.skipUnless(hasattr(os, "link"), "hard links unavailable")
    def test_fix_refuses_multiple_hard_links(self):
        first = self.write_source("src/first.py", "2024")
        second = Path("src/second.py")
        os.link(first, second)
        original = first.read_bytes()

        result = core.run(self.settings(paths=(str(first),)), "fix", CURRENT_YEAR)

        self.assertEqual(result.diagnostics[0].code, core.DiagnosticCode.UNSAFE_FIX)
        self.assertEqual(first.read_bytes(), original)
        self.assertEqual(second.read_bytes(), original)
        self.assertEqual(first.stat().st_ino, second.stat().st_ino)

    def test_fix_refuses_content_change_before_replace(self):
        path = self.write_source("src/stale.py", "2024")
        original = path.read_bytes()

        with mock.patch("validate_headers.core._matches_identity", side_effect=[True, False]):
            result = core.run(self.settings(), "fix", CURRENT_YEAR)

        self.assertEqual(result.diagnostics[0].code, core.DiagnosticCode.UNSAFE_FIX)
        self.assertEqual(path.read_bytes(), original)

    def test_discovery_deduplicates_and_applies_ignores(self):
        first = self.write_source("src/a.py")
        second = self.write_source("other/b.py")
        self.write_source("src/ignored.py", None)
        self.write_source("src/skip/bad.py", None)

        paths = core.discover_files(
            ["src", "other", "src/a.py"],
            ["ignored.py"],
            ["src/skip"],
        )

        self.assertEqual(paths, [second, first])

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_directory_scan_skips_linked_files_and_rejects_linked_roots(self):
        target = self.write_source("outside/target.py", "2024")
        Path("src").mkdir()
        linked_file = Path("src/linked.py")
        linked_root = Path("linked-root")
        try:
            linked_file.symlink_to(target.absolute())
            linked_root.symlink_to(Path("src").absolute(), target_is_directory=True)
        except OSError as error:
            self.skipTest(str(error))

        self.assertEqual(core.discover_files(["src"], [], []), [])
        result = core.run(self.settings(paths=(str(linked_root),)), "check", CURRENT_YEAR)
        self.assertEqual(result.exit_code, 2)
        if result.error is None:
            self.fail("Expected linked directory error")
        self.assertIn("Refusing symlink", result.error.message)


if __name__ == "__main__":
    unittest.main()
