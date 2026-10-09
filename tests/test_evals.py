"""The grading in evals/run_evals.py, on made-up `claude -p` transcripts. Runs no model.

The cases themselves are checked against the real results: each expected number must be what the
MCP server answers today, so the eval can't drift from the data it's testing.
"""
import importlib.util
import json
import re
import unittest

from support import ROOT  # first: it puts mcp_server/ on sys.path

import results

spec = importlib.util.spec_from_file_location("run_evals", ROOT / "evals" / "run_evals.py")
run_evals = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_evals)


def stream(*tools, answer="", subtype="success", server="connected"):
    """A minimal stream-json transcript: init, one assistant turn per tool call, then the result."""
    events = [{"type": "system", "subtype": "init", "mcp_servers": [{"name": run_evals.SERVER, "status": server}]}]
    events += [{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": run_evals.PREFIX + t, "input": {}}]}}
               for t in tools]
    events.append({"type": "result", "subtype": subtype, "is_error": subtype != "success", "result": answer, "total_cost_usd": 0.05})
    return [json.dumps(e) for e in events] + ["not json: a stray line"]


CASE = {"id": "x", "ask": "?", "expect": [r"\b28(3\.7|4)\s*%", r"\b5 of 5\b"], "tools": ["get_results", "compare_funds"]}


class Grading(unittest.TestCase):
    def test_parse_stream(self):
        run = run_evals.parse_stream(stream("compare_funds", "get_results", answer="It made **+283.7%**."))
        self.assertEqual(run, {"tools": [run_evals.PREFIX + "compare_funds", run_evals.PREFIX + "get_results"],
                               "answer": "It made **+283.7%**.", "cost_usd": 0.05, "error": None, "server": "connected"})

    def test_pass(self):
        for answer in ("+283.7% total, up 5 of 5 years", "About **284 %**; 5 of 5 years were up."):
            with self.subTest(answer):
                self.assertEqual(run_evals.grade(CASE, run_evals.parse_stream(stream("compare_funds", answer=answer))), [])

    def test_wrong_number_or_missing_words(self):
        problems = run_evals.grade(CASE, run_evals.parse_stream(stream("get_results", answer="It made 2837% in 4 of 5 years")))
        self.assertEqual(len(problems), 2)

    def test_tool_must_be_used(self):
        problems = run_evals.grade(CASE, run_evals.parse_stream(stream(answer="+283.7%, 5 of 5")))
        self.assertEqual(problems, ["expected a call to get_results or compare_funds, got none"])
        problems = run_evals.grade(CASE, run_evals.parse_stream(stream("pattern_verdict", answer="+283.7%, 5 of 5")))
        self.assertEqual(problems, ["expected a call to get_results or compare_funds, got ['pattern_verdict']"])

    def test_failed_runs_and_servers_fail(self):
        self.assertIn("the run ended with error_max_turns",
                      run_evals.grade(CASE, run_evals.parse_stream(stream("get_results", answer="283.7% 5 of 5", subtype="error_max_turns"))))
        self.assertIn("the MCP server was failed",
                      run_evals.grade(CASE, run_evals.parse_stream(stream("get_results", answer="283.7% 5 of 5", server="failed"))))
        self.assertIn("the MCP server was not reported", run_evals.grade(CASE, run_evals.parse_stream([])))

    def test_losses_with_signs_or_words(self):
        labu = next(c for c in run_evals.CASES if c["id"] == "labu-buy-and-hold")
        for answer in ("−76.8%, worst drawdown −97.1%", "-77 %, drawdown - 97%", "–76.8% and –97%",
                       "It **lost 76.8%**. Its worst drawdown was −97.1%.",  # the first eval run's answer, failed by the old grader
                       "down 77%, with a drawdown of 97%"):
            with self.subTest(answer):
                self.assertEqual(run_evals.grade(labu, run_evals.parse_stream(stream("get_results", answer=answer))), [])
        for answer in ("76.8%, 97.1%", "It gained 76.8%, a drawdown of 97.1%"):
            with self.subTest(answer):
                problems = run_evals.grade(labu, run_evals.parse_stream(stream("get_results", answer=answer)))
                self.assertIn(f"answer lacks /{labu['expect'][0]}/", problems)  # 76.8% with no sign of a loss

    def test_case_ids_unique_and_tools_real(self):
        ids = [c["id"] for c in run_evals.CASES]
        self.assertEqual(len(ids), len(set(ids)))
        for case in run_evals.CASES:
            self.assertLessEqual(set(case["tools"]), {"get_results", "compare_funds", "pattern_verdict"}, case["id"])
            for pattern in case["expect"]:
                re.compile(pattern)


@unittest.skipUnless(results.RESULTS.exists(), "needs data/soxl-labu-dpst/results_5y.json (run fetch_prices.py, analyze.py)")
class CasesMatchTheData(unittest.TestCase):
    """Each case's expected answer, as the server would give it today."""

    def expect(self, case_id, text):
        case = next(c for c in run_evals.CASES if c["id"] == case_id)
        for pattern in case["expect"]:
            self.assertRegex(run_evals.normalize(text), pattern, case_id)

    def rule(self, fund, name):
        return next(r for r in results.get_results(fund)["rules"] if r["rule"] == name)

    def test_rule_cases(self):
        rsi2 = self.rule("SOXL", "RSI(2)<10 -> exit above 5-day avg or day 10")
        self.expect("rsi2-soxl", f"{rsi2['total_return_pct']}% up {rsi2['years_up']}")
        bh = self.rule("LABU", "Buy & hold")
        self.expect("labu-buy-and-hold", f"{bh['total_return_pct']}% worst {bh['max_drawdown_pct']}%")
        three = results.compare_funds("3 down days")["rules"][0]["funds"]
        self.expect("three-down-days", " ".join(f"{f['total_return_pct']}%" for f in three.values()))
        best = results.get_results("SOXL")["rules"][0]
        self.expect("best-rule-soxl", f"{best['rule']} {best['total_return_pct']}%")

    def test_pattern_cases(self):
        out = results.pattern_verdict("")
        held = [m for m in out["matches"] if m["verdict"].startswith("held up")]
        self.expect("what-held-up", " ".join(f"{m['fund']} {m['pattern']}" for m in held))
        s = out["summary"]
        self.expect("how-many-tests", f"{s['tests']} tests, {s['p_below_0.05']} below, {s['expected_by_luck']} by luck")
        fomc = results.pattern_verdict("FOMC decision day", "SOXL")["matches"][0]
        self.assertTrue(fomc["verdict"].startswith("no evidence"))
        self.expect("fomc-soxl", f"p = {fomc['p']}: no evidence")


if __name__ == "__main__":
    unittest.main()
