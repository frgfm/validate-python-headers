# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed local sandbox executables
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).parents[2]
ANNUAL = "automation/update-copyright-years-2027"


@unittest.skipUnless(os.name == "posix" and shutil.which("bash") and shutil.which("git"), "Requires POSIX Bash and Git")
class AnnualWorkflowTestCase(unittest.TestCase):
    def test_publication_preserves_branches_and_retries(self):
        workflow = (ROOT / ".github/workflows/update-copyright-years.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "1 0 1 1 *"\n      timezone: Europe/Paris', workflow)
        self.assertIn("TZ: Europe/Paris", workflow)
        self.assertNotIn("workflow_dispatch", workflow)
        script = textwrap.dedent(workflow.rsplit("        run: |\n", 1)[1])
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        documented = readme.rsplit("        run: |\n", 1)[1].split("\n```", 1)[0]
        self.assertEqual(script.rstrip(), textwrap.dedent(documented).rstrip())

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            remote = root / "remote.git"
            clone = root / "clone"

            def run(*args, cwd=None, env=None, check=True):
                return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - fixed sandbox executables
                    args, cwd=cwd, env=env, check=check, capture_output=True, text=True
                )

            def git(*args, cwd=clone):
                return run("git", *args, cwd=cwd).stdout.strip()

            run("git", "init", "--bare", "--initial-branch=main", str(remote))
            run("git", "clone", str(remote), str(clone))
            git("config", "core.hooksPath", str(root / "no-hooks"))
            git("config", "user.name", "Fixture")
            git("config", "user.email", "fixture@example.invalid")
            (clone / "sample.py").write_text("# original fixture\n", encoding="utf-8")
            (clone / "notes.txt").write_text("original fixture\n", encoding="utf-8")
            git("add", "sample.py", "notes.txt")
            git("commit", "-m", "fixture")
            git("push", "origin", "main")
            main = git("rev-parse", "main")

            fake = root / "bin"
            fake.mkdir()
            log = root / "calls"
            programs = {
                "date": "#!/bin/sh\nprintf '2027\\n'\n",
                "make": "#!/bin/sh\n"
                + textwrap.dedent("""\
                    printf 'fix\\n' >> "$CALLS"
                    if test "$FIX_MODE" = noop; then exit 0; fi
                    printf '# updated fixture\\n' > sample.py
                    printf 'unrelated change\\n' > notes.txt
                    exit "$FIX_MODE"
                """),
                "gh": "#!/bin/sh\n"
                + textwrap.dedent("""\
                    printf '%s %s\\n' "$1" "$2" >> "$CALLS"
                    if test "$2" = list; then printf '%s' "$EXISTING_PR"; exit 0; fi
                    exit "$CREATE_EXIT"
                """),
            }
            for name, body in programs.items():
                path = fake / name
                path.write_text(body, encoding="utf-8")
                path.chmod(0o755)
            env = os.environ | {
                "PATH": str(fake) + os.pathsep + os.environ["PATH"],
                "BASE_BRANCH": "main",
                "TZ": "Europe/Paris",
                "CALLS": str(log),
                "EXISTING_PR": "",
                "FIX_MODE": "noop",
                "CREATE_EXIT": "0",
            }

            def execute(**changes):
                return run("bash", "-e", "-o", "pipefail", "-c", script, cwd=clone, env=env | changes, check=False)

            self.assertEqual(execute().returncode, 0)
            self.assertEqual(git("ls-remote", "--heads", "origin", ANNUAL), "")
            for code in ("1", "2"):
                self.assertEqual(execute(FIX_MODE=code).returncode, int(code))
                self.assertEqual(git("ls-remote", "--heads", "origin", ANNUAL), "")

            self.assertEqual(execute(FIX_MODE="0", CREATE_EXIT="1").returncode, 1)
            annual = git("rev-parse", ANNUAL)
            self.assertEqual(git("diff", "--name-only", main, annual), "sample.py")
            self.assertEqual(git("show", f"{annual}:notes.txt"), "original fixture")
            git("restore", "notes.txt")
            git("switch", "main")
            self.assertEqual(execute(FIX_MODE="2").returncode, 0)
            self.assertEqual(git("rev-parse", f"origin/{ANNUAL}"), annual)
            self.assertEqual(execute(EXISTING_PR="123", FIX_MODE="2").returncode, 0)
            self.assertEqual(git("rev-parse", "main"), main)
            self.assertEqual(git("rev-parse", f"origin/{ANNUAL}"), annual)
            self.assertEqual(log.read_text(encoding="utf-8").count("fix\n"), 4)


if __name__ == "__main__":
    unittest.main()
