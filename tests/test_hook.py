"""The Claude Code hook in .claude/hooks/run_tests.py, fed the JSON that Claude Code sends after an edit.

Each test points the hook at a throwaway project with one tiny test file, so the hook never runs
this test suite from inside itself.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from support import ROOT

HOOK = ROOT / ".claude" / "hooks" / "run_tests.py"
PASSING = "import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        pass\n"
FAILING = "import unittest\n\nclass T(unittest.TestCase):\n    def test_sum(self):\n        self.assertEqual(1 + 1, 3)\n"


class Hook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = pathlib.Path(self.tmp.name).resolve()
        (self.project / "tests").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def edit(self, path, test_file=FAILING, tool="Edit"):
        """Run the hook as if Claude had just edited `path`; return its exit code and parsed output."""
        (self.project / "tests" / "test_tiny.py").write_text(test_file)
        event = {"tool_name": tool, "tool_input": {"file_path": str(self.project / path)}}
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.project))
        p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event), env=env,
                           capture_output=True, text=True, timeout=60)
        return p.returncode, json.loads(p.stdout) if p.stdout.strip() else None

    def test_failures_go_to_claude(self):
        code, out = self.edit("backtests/soxl-labu-dpst/analyze.py")
        self.assertEqual(code, 0)
        self.assertEqual(out["decision"], "block")
        self.assertIn("backtests/soxl-labu-dpst/analyze.py", out["reason"])
        self.assertIn("test_sum", out["reason"])
        self.assertIn("FAILED", out["reason"])

    def test_every_watched_folder(self):
        for path in ("studies/soxl-labu-dpst/LEV3X_Dip_STUDY.ts", "tests/test_statistics.py"):
            with self.subTest(path):
                self.assertEqual(self.edit(path, tool="Write")[1]["decision"], "block")

    def test_silent_when_tests_pass(self):
        self.assertEqual(self.edit("backtests/soxl-labu-dpst/analyze.py", PASSING), (0, None))

    def test_ignores_other_files(self):
        for path in ("README.md", "notes/soxl-labu-dpst-5yr-retest.md", "backtests.md", "/etc/hosts"):
            with self.subTest(path):
                self.assertEqual(self.edit(path), (0, None))

    def test_ignores_input_it_cant_read(self):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.project))
        for stdin in ("not json", "{}", '{"tool_input": {}}'):
            with self.subTest(stdin):
                p = subprocess.run([sys.executable, str(HOOK)], input=stdin, env=env, capture_output=True, text=True)
                self.assertEqual((p.returncode, p.stdout), (0, ""))


class Settings(unittest.TestCase):
    def test_hook_is_registered(self):
        settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
        entries = [e for e in settings["hooks"]["PostToolUse"] if e["matcher"] == "Edit|Write"]
        commands = [h["command"] for e in entries for h in e["hooks"] if h["type"] == "command"]
        self.assertEqual(len(commands), 1)
        self.assertIn(".claude/hooks/run_tests.py", commands[0])


if __name__ == "__main__":
    unittest.main()
