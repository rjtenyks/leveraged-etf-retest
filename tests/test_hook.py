"""The Claude Code hook in .claude/hooks/run_tests.py, fed the JSON that Claude Code sends after an edit.

Each test points the hook at a throwaway project with one tiny test file, so the hook never runs
this test suite from inside itself.
"""
import json
import os
import pathlib
import py_compile
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
        p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event), env=self.env(),
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

    def env(self):
        """The environment of a plain Claude Code session in the throwaway project."""
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPYCACHEPREFIX", "PYTHONDONTWRITEBYTECODE")}
        return dict(env, CLAUDE_PROJECT_DIR=str(self.project))

    def test_fresh_bytecode_after_a_same_length_edit(self):
        # The trap: a cached .pyc of the old code, and new code of the same size with the same timestamp.
        calc = self.project / "tests" / "calc.py"
        calc.write_text("VALUE = 1\n")
        cached = calc.parent / "__pycache__" / f"calc.{sys.implementation.cache_tag}.pyc"
        py_compile.compile(calc, cfile=cached, invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
        old = calc.stat()
        calc.write_text("VALUE = 2\n")
        os.utime(calc, ns=(old.st_atime_ns, old.st_mtime_ns))
        test = "import unittest\nimport calc\n\nclass T(unittest.TestCase):\n    def test_value(self):\n        self.assertEqual(calc.VALUE, 1)\n"
        out = self.edit("tests/calc.py", test)[1]
        self.assertIsNotNone(out, "the hook ran the stale cached code (VALUE = 1) instead of the edit")
        self.assertEqual(out["decision"], "block")

    def test_ignores_input_it_cant_read(self):
        env = self.env()
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
