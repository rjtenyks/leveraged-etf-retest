"""The MCP server's answers (mcp_server/results.py), on a small hand-made results file.

Standard library only: these run in CI, which has neither the downloaded prices nor needs the mcp package
for them. The last class checks the real results against the README, and skips when they aren't there.
"""
import json
import pathlib
import tempfile
import unittest
from unittest import mock

import support  # noqa: F401  (puts mcp_server/ on sys.path)
import results
from results import ResultsError


def rule(total, years, open_trade=None):
    return {"total": total, "cagr": round(total / 10, 1), "max_dd": -50.0, "years": years, "trades": 10,
            "win_rate": 60.0, "avg_trade": 1.5, "exposure": 20.0, "open_trade": open_trade, "curve": []}


def fund(base):
    return {"backtests": {
        "Buy & hold": rule(base, [10.0, -5.0, 20.0, 30.0, -1.0], ["2021-10-06", base]),
        "RSI(2)<10 -> exit above 5-day avg": rule(base + 50, [1.0, 2.0, 3.0, 4.0, 5.0]),
        "3 down days -> exit first up day": rule(base + 100, [5.0, 0.0, None, -2.0, 9.0]),
        "Down >=2-sigma day -> hold 3 days": rule(base - 10, [-1.0, -1.0, -1.0, -1.0, -1.0]),
    }}


FIXTURE = {
    "window": ["2021-10-07", "2026-10-06"],
    "funds": {"SOXL": fund(100.0), "LABU": fund(-20.0), "DPST": fund(5.0)},
    "fdr": {"n_tests": 6, "n_p_below_05": 2, "expected_by_chance": 0.3, "n_survive_q10": 1, "tests": [
        ["SOXL", "fed", "Day after FOMC", 0.9, 0.9],
        ["LABU", "signal", "RSI(2) below 10 (next day)", 0.0499, 0.10],  # p just under 0.05, q exactly 0.10
        ["SOXL", "last30", "Up 6%+ at 3:30", 0.0002, 0.0012],
        ["DPST", "fed", "FOMC decision day", 0.05, 0.15],  # p exactly 0.05
        ["SOXL", "signal", "RSI(2) below 10 (next 5 days)", 0.2, 0.4],
        ["LABU", "weekday", "Tue", 0.6, 0.7],
    ]},
}


class Tools(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = pathlib.Path(tmp.name) / "results_5y.json"
        self.path.write_text(json.dumps(FIXTURE))
        patch = mock.patch.object(results, "RESULTS", self.path)
        patch.start()
        self.addCleanup(patch.stop)

    def test_get_results_ranks_the_rules(self):
        out = results.get_results(" soxl ")
        self.assertEqual(out["fund"], "SOXL")
        self.assertEqual(out["window"], {"start": "2021-10-07", "end": "2026-10-06"})
        self.assertEqual([r["total_return_pct"] for r in out["rules"]], [200.0, 150.0, 100.0, 90.0])
        self.assertEqual(out["rules"][0]["rule"], "3 down days -> exit first up day")
        self.assertNotIn("curve", out["rules"][0])

    def test_years_up_and_open_trades(self):
        rules = {r["rule"]: r for r in results.get_results("SOXL")["rules"]}
        self.assertEqual(rules["Buy & hold"]["years_up"], "3 of 5")
        self.assertEqual(rules["3 down days -> exit first up day"]["years_up"], "2 of 5")  # 0.0 and a missing year aren't up
        self.assertEqual(rules["RSI(2)<10 -> exit above 5-day avg"]["years_up"], "5 of 5")
        self.assertEqual(rules["Buy & hold"]["open_at_end"], {"entered": "2021-10-06", "return_pct": 100.0})
        self.assertIsNone(rules["RSI(2)<10 -> exit above 5-day avg"]["open_at_end"])

    def test_unknown_fund(self):
        for call in (lambda: results.get_results("TQQQ"), lambda: results.pattern_verdict("", "TQQQ")):
            with self.assertRaisesRegex(ResultsError, "Unknown fund 'TQQQ'.*SOXL, LABU, DPST"):
                call()

    def test_missing_results_say_how_to_make_them(self):
        self.path.unlink()
        for call in (lambda: results.get_results("SOXL"), lambda: results.compare_funds("rsi"),
                     lambda: results.pattern_verdict("")):
            with self.assertRaisesRegex(ResultsError, "fetch_prices.py, then analyze.py"):
                call()

    def test_compare_funds_side_by_side(self):
        out = results.compare_funds("3 down days")
        self.assertEqual(len(out["rules"]), 1)  # not the 2-sigma rule, which has the same words in another order
        self.assertEqual({f: s["total_return_pct"] for f, s in out["rules"][0]["funds"].items()},
                         {"SOXL": 200.0, "LABU": 80.0, "DPST": 105.0})

    def test_rule_names_found_loosely(self):
        for query, want in (("buy and hold", ["Buy & hold"]), ("RSI(2)", ["RSI(2)<10 -> exit above 5-day avg"]),
                            ("rsi 2", ["RSI(2)<10 -> exit above 5-day avg"]), ("2-sigma", ["Down >=2-sigma day -> hold 3 days"]),
                            ("hold", ["Buy & hold", "Down >=2-sigma day -> hold 3 days"]), ("days down 3", ["3 down days -> exit first up day", "Down >=2-sigma day -> hold 3 days"])):
            with self.subTest(query):
                self.assertEqual([r["rule"] for r in results.compare_funds(query)["rules"]], want)

    def test_unknown_rule_lists_the_rules(self):
        for query in ("moon phase", "", "the rule"):
            with self.subTest(query), self.assertRaisesRegex(ResultsError, "No rule matches.*Buy & hold; RSI"):
                results.compare_funds(query)

    def test_verdicts_at_the_thresholds(self):
        found = {(m["fund"], m["pattern"]): m["verdict"] for m in results.pattern_verdict("")["matches"]}
        self.assertTrue(found[("SOXL", "Up 6%+ at 3:30")].startswith("held up"))
        self.assertTrue(found[("LABU", "RSI(2) below 10 (next day)")].startswith("probably luck"))  # q = 0.10 isn't below 0.10
        self.assertTrue(found[("DPST", "FOMC decision day")].startswith("no evidence"))  # p = 0.05 isn't below 0.05
        self.assertTrue(found[("SOXL", "Day after FOMC")].startswith("no evidence"))

    def test_patterns_smallest_p_first_with_the_summary(self):
        out = results.pattern_verdict("")
        self.assertEqual([m["p"] for m in out["matches"]], [0.0002, 0.0499, 0.05, 0.2, 0.6, 0.9])
        self.assertEqual(out["summary"], {"tests": 6, "p_below_0.05": 2, "expected_by_luck": 0.3, "survive_false_discovery_check": 1})
        self.assertEqual(out["more_matches"], 0)

    def test_patterns_by_query_and_fund(self):
        self.assertEqual([(m["fund"], m["pattern"]) for m in results.pattern_verdict("fomc")["matches"]],
                         [("DPST", "FOMC decision day"), ("SOXL", "Day after FOMC")])
        self.assertEqual([m["pattern"] for m in results.pattern_verdict("FOMC", fund="soxl")["matches"]], ["Day after FOMC"])
        self.assertEqual([m["family"] for m in results.pattern_verdict("signal")["matches"]], ["signal", "signal"])

    def test_unknown_pattern_suggests_queries(self):
        with self.assertRaisesRegex(ResultsError, "No pattern test matches 'moon'.*fed, last30, signal, weekday"):
            results.pattern_verdict("moon")
        with self.assertRaisesRegex(ResultsError, "on DPST"):
            results.pattern_verdict("Tue", fund="DPST")

    def test_long_lists_are_cut_and_counted(self):
        with mock.patch.object(results, "MAX_PATTERNS", 2):
            out = results.pattern_verdict("")
        self.assertEqual(len(out["matches"]), 2)
        self.assertEqual(out["more_matches"], 4)


@unittest.skipUnless(results.RESULTS.exists(), "needs data/soxl-labu-dpst/results_5y.json (run fetch_prices.py, analyze.py)")
class RealResults(unittest.TestCase):
    """The answers agree with the README and with the counts analyze.py saved."""

    def test_readme_rsi2_rule(self):
        rules = {r["rule"]: r for r in results.get_results("SOXL")["rules"]}
        rsi2 = rules["RSI(2)<10 -> exit above 5-day avg or day 10"]
        self.assertEqual(round(rsi2["total_return_pct"]), 284)
        self.assertEqual(round(rsi2["max_drawdown_pct"]), -62)
        self.assertEqual(rsi2["years_up"], "5 of 5")

    def test_pattern_counts(self):
        out = results.pattern_verdict("")
        self.assertEqual(out["summary"], {"tests": 189, "p_below_0.05": 6, "expected_by_luck": 9.5, "survive_false_discovery_check": 1})
        self.assertEqual(len(out["matches"]) + out["more_matches"], 189)
        verdicts = [m["verdict"] for m in out["matches"]]
        self.assertEqual(sum(v.startswith("held up") for v in verdicts), 1)
        self.assertEqual(sum(v.startswith(("held up", "probably luck")) for v in verdicts), 6)
        self.assertEqual((out["matches"][0]["fund"], out["matches"][0]["pattern"]), ("SOXL", "Up 6%+ at 3:30"))


if __name__ == "__main__":
    unittest.main()
