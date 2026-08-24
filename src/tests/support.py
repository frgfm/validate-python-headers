# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

import io
import os
import stat
import sys
import unittest
from contextlib import chdir
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

sys.path.insert(0, str(Path(__file__).parents[1]))

from validate_headers import cli
from validate_headers.core import Settings

OWNER = "Example Owner"
CURRENT_YEAR = 2030
APACHE_NOTICE = (
    "# This program is licensed under the Apache License 2.0.\n"
    "# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.\n"
)


class WorkspaceTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.root = Path(self.temporary_directory.name).resolve()
        self.change_directory = chdir(self.root)
        self.change_directory.__enter__()
        Path("LICENSE").write_text("Apache-2.0\n", encoding="utf-8")

    def tearDown(self):
        self.change_directory.__exit__(None, None, None)
        self.temporary_directory.cleanup()

    def settings(self, **overrides):
        values = {
            "owner": OWNER,
            "year": 2022,
            "license": "Apache-2.0",
            "license_notice": None,
            "license_path": self.root / "LICENSE",
            "paths": ("src",),
            "ignore_files": (),
            "ignore_folders": (),
            "project_root": self.root,
            "config_path": None,
        }
        values.update(overrides)
        return Settings(**values)

    def write_source(
        self,
        path,
        years="2030",
        *,
        owner=OWNER,
        notice=APACHE_NOTICE,
        preamble=(),
        newline="\n",
        body="value = 'café'\n",
        bom=False,
    ):
        source_path = Path(path)
        source_path.parent.mkdir(parents=True, exist_ok=True)
        if years is None:
            source = body
        else:
            header: list[str] = list(preamble)
            if header:
                header.append("\n")
            header.extend([f"# Copyright (C) {years}, {owner}.\n", "\n", notice])
            source = "".join(header) + "\n" + body
        raw_source = source.replace("\n", newline).encode()
        if bom:
            raw_source = b"\xef\xbb\xbf" + raw_source
        source_path.write_bytes(raw_source)
        return source_path

    def capture_main(self, argv, *, github_output=None):
        stdout = io.StringIO()
        stderr = io.StringIO()
        environment = {} if github_output is None else {"GITHUB_OUTPUT": str(github_output)}
        with (
            mock.patch("sys.stdout", stdout),
            mock.patch("sys.stderr", stderr),
            mock.patch.dict(os.environ, environment, clear=False),
        ):
            if github_output is None:
                os.environ.pop("GITHUB_OUTPUT", None)
            exit_code = cli.main(argv)
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def assert_mode(self, path, expected):
        self.assertEqual(stat.S_IMODE(Path(path).stat().st_mode), expected)
