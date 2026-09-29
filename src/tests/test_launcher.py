# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

import os
import runpy
import subprocess  # ruff: ignore[suspicious-subprocess-import] - mocked launcher calls
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

with mock.patch.object(sys, "path", [str(Path(__file__).parents[1]), *sys.path]):
    from lint_my_headers.cli import _find_binary, main


class LauncherTestCase(unittest.TestCase):
    def test_binary_is_found_only_in_distribution_metadata(self):
        with TemporaryDirectory() as directory:
            binary = Path(directory) / ("lmh.exe" if sys.platform == "win32" else "lmh")
            binary.touch()
            distribution = mock.Mock(files=[Path("unrelated"), Path(binary.name)])
            distribution.locate_file.return_value = binary
            with mock.patch("importlib.metadata.distribution", return_value=distribution):
                self.assertEqual(_find_binary(), binary)
                binary.unlink()
                with self.assertRaises(FileNotFoundError):
                    _find_binary()

    def test_callable_preserves_arguments_exit_codes_and_returns(self):
        binary = Path("native executable").absolute()
        args = ["check", "a file;$(echo literal)&.py"]
        with mock.patch("lint_my_headers.cli._find_binary", return_value=binary):
            for code in (0, 1, 2):
                with mock.patch.object(subprocess, "run", return_value=mock.Mock(returncode=code)) as run:
                    self.assertEqual(main(args), code)
                    run.assert_called_once_with([str(binary), *args], check=False)
            with mock.patch.object(subprocess, "run", side_effect=KeyboardInterrupt):
                self.assertEqual(main(args), 2)

    def test_module_execs_on_unix_but_uses_callable_on_windows(self):
        entry = Path(__file__).parents[1] / "lint_my_headers/__main__.py"
        binary = str(Path("native executable").absolute())
        for platform in ("linux", "darwin", "win32"):
            with (
                self.subTest(platform=platform),
                mock.patch.object(sys, "platform", platform),
                mock.patch.object(sys, "argv", [str(entry), "check", "a b.py"]),
                mock.patch("lint_my_headers.cli._find_binary", return_value=binary),
                mock.patch("lint_my_headers.cli.main", return_value=2) as main_call,
                mock.patch.object(os, "execv", side_effect=SystemExit(2)) as execute,
                self.assertRaises(SystemExit) as raised,
            ):
                runpy.run_path(str(entry), run_name="lint_my_headers.__main__")
            self.assertEqual(raised.exception.code, 2)
            if platform == "win32":
                main_call.assert_called_once_with()
                execute.assert_not_called()
            else:
                execute.assert_called_once_with(binary, [binary, "check", "a b.py"])
                main_call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
