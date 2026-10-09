"""The numbers-auditor agent (.claude/agents/numbers-auditor.md) and its eval (evals/eval_auditor.py). Runs no model.

The agent must stay read-only: several of them run at once on the same files, with no worktrees.
"""
import json
import pathlib
import re
import sys
import tempfile
import unittest

from support import ROOT

sys.path.insert(0, str(ROOT / "evals"))
import eval_auditor  # noqa: E402  (it imports run_evals from the same folder)

AGENT = ROOT / ".claude" / "agents" / "numbers-auditor.md"
SERVER = next(iter(json.loads((ROOT / ".mcp.json").read_text())["mcpServers"]))


def frontmatter(path):
    head, body = re.match(r"---\n(.*?)\n---\n(.*)", path.read_text(), re.S).groups()
    return dict(line.split(": ", 1) for line in head.splitlines()), body


class Agent(unittest.TestCase):
    def setUp(self):
        self.head, self.body = frontmatter(AGENT)

    def test_header(self):
        self.assertEqual(self.head["name"], AGENT.stem)
        self.assertIn("in parallel", self.head["description"])
        self.assertIn(self.head["model"], {"sonnet", "opus", "haiku", "fable", "inherit"})

    def test_read_only(self):
        tools = {t.strip() for t in self.head["tools"].split(",")}
        self.assertEqual(tools, {"Read", "Grep", "Glob", f"mcp__{SERVER}"})  # no Edit, Write or Bash

    def test_instructions_name_every_server_tool(self):
        server_tools = re.findall(r"@server\.tool\([^)]*\)\ndef (\w+)", (ROOT / "mcp_server" / "server.py").read_text())
        self.assertEqual(len(server_tools), 4)
        for tool in server_tools:
            self.assertIn(f"`{tool}", self.body, f"tell the auditor when to use {tool}")

    def test_report_format_is_what_the_eval_reads(self):
        example = re.search(r"```json\n(.*?)\n```", self.body, re.S).group(1)
        report = eval_auditor.parse_report(f"```json\n{example}\n```")
        self.assertEqual(set(report), {"checked", "mismatches", "not_found", "not_from_results"})
        self.assertEqual(set(report["mismatches"][0]), {"file", "line", "text", "written", "actual", "source"})


class Eval(unittest.TestCase):
    def test_groups_cover_the_documents(self):
        grouped = {f for files in eval_auditor.GROUPS.values() for f in files}
        wanted = {"README.md"} | {p.relative_to(ROOT).as_posix() for p in (ROOT / "notes").glob("*.md")} \
            | {p.relative_to(ROOT).as_posix() for p in (ROOT / "studies").rglob("*") if p.is_file()}  # README.txt too
        self.assertEqual(grouped, wanted)
        self.assertLessEqual({p["file"] for p in eval_auditor.PLANTED}, grouped)

    def test_plants_still_apply_to_the_documents(self):
        """A document edit can't quietly stop a planted error from being planted."""
        with tempfile.TemporaryDirectory() as folder:
            eval_auditor.copy_project(folder)
            self.assertTrue((pathlib.Path(folder) / ".claude" / "agents" / "numbers-auditor.md").exists())
            lines = eval_auditor.plant(folder)
            for p, line in zip(eval_auditor.PLANTED, lines):
                with self.subTest(p["new"]):
                    self.assertNotEqual(p["old"], p["new"])
                    self.assertIn(p["wrong"].lstrip("+"), eval_auditor.numbers(p["new"]))
                    self.assertIn(p["new"], (pathlib.Path(folder) / p["file"]).read_text().splitlines()[line - 1])

    def test_plant_line_is_where_the_old_text_was(self):
        with tempfile.TemporaryDirectory() as folder:
            (pathlib.Path(folder) / "a.md").write_text("intro +49%\nmore\nthe rule: -49%\n")  # the new text is already on line 1
            self.assertEqual(eval_auditor.plant(folder, [{"file": "a.md", "old": "-49%", "new": "+49%", "wrong": "+49"}]), [3])

    def test_an_ambiguous_plant_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            (pathlib.Path(folder) / "a.md").write_text("+284% and +284%")
            with self.assertRaisesRegex(ValueError, "appears 2 times"):
                eval_auditor.plant(folder, [{"file": "a.md", "old": "+284%", "new": "+248%", "wrong": "248"}])

    def test_parse_report(self):
        report = {"checked": 3, "mismatches": [], "not_found": [], "not_from_results": 1}
        for text in (f"```json\n{json.dumps(report)}\n```\n\nEverything matches.", json.dumps(report),
                     f"Here it is: {json.dumps(report)}"):
            with self.subTest(text[:20]):
                self.assertEqual(eval_auditor.parse_report(text), report)
        malformed = [{"checked": 3}, dict(report, mismatches=["README.md:33 +248%"]), dict(report, not_found=None),
                     dict(report, checked="3"), dict(report, mismatches=[{"file": "README.md", "written": "+248%"}])]
        for text in ["no report", "```json\n{broken\n```"] + [json.dumps(m) for m in malformed]:
            with self.subTest(text[:60]):
                self.assertIsNone(eval_auditor.parse_report(text))

    def test_numbers_keep_their_signs(self):
        self.assertEqual(eval_auditor.numbers("\u22120.16% on average"), {"-0.16"})
        self.assertEqual(eval_auditor.numbers("SOXL +49%, 2 of 5"), {"49", "2", "5"})

    def test_one_report_catches_one_plant(self):
        # The code review's case: the README's two plants are on adjacent lines, and one report caught both.
        planted = [{"file": "README.md", "wrong": "248"}, {"file": "README.md", "wrong": "585"}]
        result = eval_auditor.score([{"file": "README.md", "line": 33, "written": "+248%"}], planted, [33, 34])
        self.assertEqual(result["caught"], 1)
        self.assertEqual(result["missed"], planted[1:])  # +585% wasn't reported: it's missed, not caught by the +248% report

    def test_the_quoted_number_outranks_the_line(self):
        planted = [{"file": "README.md", "wrong": "248"}, {"file": "README.md", "wrong": "585"}]
        report = {"file": "README.md", "line": 33, "written": "+248%"}  # on the +585% plant's line, but quoting +248%
        result = eval_auditor.score([report], planted, [32, 33])
        self.assertEqual(result["missed"], planted[1:])

    def test_a_number_must_match_with_its_sign(self):
        # The code review's case: "-37%" on another line used to count as catching the planted "37% won".
        planted = [{"file": "studies/soxl-labu-dpst/LEV3X_Dip_STUDY.ts", "wrong": "37"}]
        wrong = {"file": "studies/soxl-labu-dpst/LEV3X_Dip_STUDY.ts", "line": 113, "written": "-37%"}
        result = eval_auditor.score([wrong], planted, [109])
        self.assertEqual((result["caught"], result["extra"]), (0, [wrong]))

    def test_bare_file_names_match(self):
        self.assertTrue(eval_auditor.same_file("LEV3X_Dip_STUDY.ts", "studies/soxl-labu-dpst/LEV3X_Dip_STUDY.ts"))
        self.assertTrue(eval_auditor.same_file("/tmp/x/studies/soxl-labu-dpst/LEV3X_Dip_STUDY.ts", "studies/soxl-labu-dpst/LEV3X_Dip_STUDY.ts"))
        self.assertTrue(eval_auditor.same_file("./README.md", "README.md"))
        self.assertFalse(eval_auditor.same_file("notes/README.md", "studies/README.md"))
        self.assertFalse(eval_auditor.same_file("XREADME.md", "README.md"))

    def test_score(self):
        planted = [{"file": "README.md", "wrong": "248"}, {"file": "notes/n.md", "wrong": "702"}]
        mismatches = [
            {"file": "/tmp/x/README.md", "line": 33, "written": "+248%"},  # another line, but it quotes the number
            {"file": "notes/n.md", "line": 99, "written": "702 full days"},  # wrong line, but it quotes the number
            {"file": "notes/n.md", "line": 5, "written": "+16%"},  # not planted: a false alarm, or a real error
            {"file": "README.md", "line": 50, "written": "702"},  # the right number in the wrong file isn't a catch
        ]
        result = eval_auditor.score(mismatches, planted, [32, 8])
        self.assertEqual((result["caught"], result["planted"], result["missed"]), (2, 2, []))
        self.assertEqual([m["line"] for m in result["extra"]], [5, 50])
        self.assertEqual(eval_auditor.score(mismatches[2:3], planted, [32, 8])["missed"], planted)


if __name__ == "__main__":
    unittest.main()
