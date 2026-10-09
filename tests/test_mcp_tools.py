"""The MCP server's answers (mcp_server/results.py), on a small hand-made results file.

Standard library only: these run in CI, which has neither the downloaded prices nor needs the mcp package
for them. The last class checks the real results against the README, and skips when they aren't there.
"""
import json
import pathlib
import re
import tempfile
import unittest
from unittest import mock

import support  # noqa: F401  (puts mcp_server/ and the backtest scripts on sys.path)
import results
from results import ResultsError


def rule(total, years, open_trade=None, trades=10):
    return {"total": total, "cagr": round(total / 10, 1), "max_dd": -50.0, "years": years, "trades": trades,
            "win_rate": 60.0, "avg_trade": 1.5, "exposure": 20.0, "open_trade": open_trade, "curve": []}


def fund(base, without=()):
    rules = {
        "Buy & hold": rule(base, [10.0, -5.0, 20.0, 30.0, -1.0], ["2021-10-06", base]),
        "RSI(2)<10 -> exit above 5-day avg": rule(base + 50, [1.0, 2.0, 3.0, 4.0, 5.0]),
        "3 down days -> exit first up day": rule(base + 100, [5.0, 0.0, None, -2.0, 9.0]),
        "Down >=2-sigma day -> hold 3 days": rule(base - 10, [-1.0, -1.0, -1.0, -1.0, -1.0]),
        "Overnight only, before costs": rule(base + 5, [1.0, 1.0, 1.0, 1.0, 1.0], trades=0),
    }
    return {"backtests": {name: r for name, r in rules.items() if name not in without}}


FIXTURE = {
    "window": ["2021-10-07", "2026-10-06"],
    "funds": {"SOXL": dict(fund(100.0), structure={"sessions": 1254, "gaps": [{"bucket": "gap <= -5%", "n": 115, "fill_rate": 27.0}]},
                           current={"date": "2026-10-06", "close": 164.26, "rsi2": 25.8, "rsi14": 55.0, "z20": 0.4,
                                    "dd20": -6.1, "sd60": 5.2, "vix": 17.1}),
              "LABU": fund(-20.0), "DPST": fund(5.0, without=["Down >=2-sigma day -> hold 3 days"])},
    "fdr": {"n_tests": 8, "n_p_below_05": 3, "expected_by_chance": 0.4, "n_survive_q10": 2, "tests": [
        ["SOXL", "fed", "Day after FOMC", 0.9, 0.9],
        ["LABU", "signal", "RSI(2) below 10 (next day)", 0.0499, 0.10],  # p just under 0.05, q exactly 0.10
        ["SOXL", "last30", "Up 6%+ at 3:30", 0.0002, 0.0012],
        ["DPST", "fed", "FOMC decision day", 0.05, 0.15],  # p exactly 0.05
        ["SOXL", "signal", "RSI(2) below 10 (next 5 days)", 0.2, 0.4],
        ["LABU", "weekday", "Tue", 0.6, 0.7],
        ["SOXL", "weekday", "Mon", 0.3, 0.8],
        ["SOXL", "week", "Week low on Monday or Friday", 0.0499612, 0.0999634],  # 3 digits would show 0.05 and 0.1
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
        self.assertEqual((out["window"]["start"], out["window"]["end"]), ("2021-10-07", "2026-10-06"))
        self.assertEqual([r["total_return_pct"] for r in out["rules"]], [200.0, 150.0, 105.0, 100.0, 90.0])
        self.assertEqual(out["rules"][0]["rule"], "3 down days -> exit first up day")
        self.assertNotIn("curve", out["rules"][0])

    def test_years_up_and_open_trades(self):
        rules = {r["rule"]: r for r in results.get_results("SOXL")["rules"]}
        self.assertEqual(rules["Buy & hold"]["years_up"], "3 of 5")
        self.assertEqual(rules["3 down days -> exit first up day"]["years_up"], "2 of 5")  # 0.0 and a missing year aren't up
        self.assertEqual(rules["RSI(2)<10 -> exit above 5-day avg"]["years_up"], "5 of 5")
        self.assertEqual(rules["Buy & hold"]["open_at_end"], {"entered": "2021-10-06", "return_pct": 100.0})
        self.assertIsNone(rules["RSI(2)<10 -> exit above 5-day avg"]["open_at_end"])

    def test_how_each_rule_trades(self):
        rules = {r["rule"]: r for r in results.get_results("SOXL")["rules"]}
        self.assertEqual(rules["RSI(2)<10 -> exit above 5-day avg"]["how_it_trades"], "buys and sells at the close, 0.05% cost per side")
        self.assertEqual(rules["RSI(2)<10 -> exit above 5-day avg"]["trades"], 10)
        overnight = rules["Overnight only, before costs"]
        self.assertIn("from the close to the next open", overnight["how_it_trades"])
        self.assertIn("no costs", overnight["how_it_trades"])
        self.assertIsNone(overnight["trades"])  # a round trip every day, which analyze.py doesn't count: not 0 trades
        self.assertEqual(results.rule_summary("A new rule", rule(1.0, [1.0] * 5))["how_it_trades"], "not recorded")

    def test_unknown_fund(self):
        for call in (lambda: results.get_results("TQQQ"), lambda: results.pattern_verdict("", "TQQQ")):
            with self.assertRaisesRegex(ResultsError, "Unknown fund 'TQQQ'.*SOXL, LABU, DPST"):
                call()

    def test_unusable_results_say_how_to_fix_them(self):
        old = dict(FIXTURE, fdr={k: v for k, v in FIXTURE["fdr"].items() if k != "tests"})  # before fdr.tests existed
        for name, text in (("half-written", json.dumps(FIXTURE)[:500]), ("older analyze.py", json.dumps(old)),
                           ("not results", "[]"), ("no funds", json.dumps(dict(FIXTURE, funds={}))), ("missing", None)):
            if text is None:
                self.path.unlink()
            else:
                self.path.write_text(text)
            for call in (lambda: results.get_results("SOXL"), lambda: results.compare_funds("rsi"), lambda: results.pattern_verdict("")):
                with self.subTest(name), self.assertRaisesRegex(ResultsError, "fetch_prices.py, then analyze.py"):
                    call()

    def test_compare_funds_side_by_side(self):
        out = results.compare_funds("3 down days")
        self.assertEqual([r["rule"] for r in out["rules"]],
                         ["3 down days -> exit first up day", "Down >=2-sigma day -> hold 3 days"])  # the asked order first
        self.assertEqual({f: s["total_return_pct"] for f, s in out["rules"][0]["funds"].items()},
                         {"SOXL": 200.0, "LABU": 80.0, "DPST": 105.0})
        self.assertIsNone(out["rules"][1]["funds"]["DPST"])  # DPST lacks that rule

    def test_rule_names_found_loosely(self):
        for query, want in (("buy and hold", ["Buy & hold"]), ("RSI(2)", ["RSI(2)<10 -> exit above 5-day avg"]),
                            ("rsi 2", ["RSI(2)<10 -> exit above 5-day avg"]), ("2-sigma", ["Down >=2-sigma day -> hold 3 days"]),
                            ("down day", ["3 down days -> exit first up day", "Down >=2-sigma day -> hold 3 days"]),
                            ("hold", ["Buy & hold", "Down >=2-sigma day -> hold 3 days"]),
                            ("overnight", ["Overnight only, before costs"])):
            with self.subTest(query):
                self.assertEqual([r["rule"] for r in results.compare_funds(query)["rules"]], want)

    def test_unknown_rule_lists_the_rules(self):
        for query in ("moon phase", "", "the rule"):
            with self.subTest(query), self.assertRaisesRegex(ResultsError, "No rule matches.*Buy & hold; RSI"):
                results.compare_funds(query)

    def test_day_names_find_the_short_names(self):
        for query, want in (("Monday", ["Week low on Monday or Friday", "Mon"]), ("Tuesday", ["Tue"]),
                            ("Tuesday effect", ["Tue"]), ("tue", ["Tue"])):
            with self.subTest(query):
                self.assertEqual([m["pattern"] for m in results.pattern_verdict(query)["matches"]], want)

    def test_what_years_mean_goes_with_every_answer(self):
        # Haiku read "2021-2023" as calendar years; the yearly values are Oct 7 to Oct 6.
        for out in (results.get_results("SOXL"), results.compare_funds("hold"), results.get_section("SOXL", "current")):
            self.assertIn("year 1 runs 2021-10-07 to 2022-10-06", out["window"]["years"])
        self.assertIn('"Y3": [average %, days]', results.SECTIONS["intraday"]["last30"])

    def test_get_section_with_its_glossary(self):
        out = results.get_section(" soxl ", " Current ")
        self.assertEqual((out["fund"], out["section"]), ("SOXL", "current"))
        self.assertEqual(out["data"]["rsi2"], 25.8)
        self.assertEqual(out["fields"], results.SECTIONS["current"])
        self.assertEqual(out["window"]["start"], "2021-10-07")

    def test_a_section_from_an_older_analyze_py(self):
        # The fixture's structure section has only sessions and gaps: like a file written before newer fields.
        with self.assertRaisesRegex(ResultsError, "older than this code: SOXL's structure section lacks .*largest_up.*analyze.py"):
            results.get_section("SOXL", "structure")

    def test_unknown_or_missing_section(self):
        for section in ("backtests", "moon", ""):
            with self.subTest(section), self.assertRaisesRegex(ResultsError, "The sections are: structure, signals.*get_results"):
                results.get_section("SOXL", section)
        with self.assertRaisesRegex(ResultsError, "LABU has no structure section.*analyze.py"):
            results.get_section("LABU", "structure")
        with self.assertRaisesRegex(ResultsError, "Unknown fund 'TQQQ'"):
            results.get_section("TQQQ", "structure")

    def test_verdicts_at_the_thresholds(self):
        found = {(m["fund"], m["pattern"]): m["verdict"] for m in results.pattern_verdict("")["matches"]}
        self.assertTrue(found[("SOXL", "Up 6%+ at 3:30")].startswith("held up"))
        self.assertTrue(found[("SOXL", "Week low on Monday or Friday")].startswith("held up"))  # q just under 0.10
        self.assertTrue(found[("LABU", "RSI(2) below 10 (next day)")].startswith("probably luck"))  # q = 0.10 isn't below 0.10
        self.assertTrue(found[("DPST", "FOMC decision day")].startswith("no evidence"))  # p = 0.05 isn't below 0.05
        self.assertTrue(found[("SOXL", "Day after FOMC")].startswith("no evidence"))

    def test_shown_numbers_agree_with_their_verdicts(self):
        week = results.pattern_verdict("week low")["matches"][0]
        self.assertEqual((week["p"], week["q"]), (0.04996, 0.09996))  # 4 digits: not 0.05 and 0.1 next to "q < 0.10"
        self.assertEqual(results.shown(0.0996, 0.10), 0.0996)
        self.assertEqual(results.shown(0.255555, 0.05), 0.256)
        self.assertEqual(results.shown(0.000204799, 0.05), 0.000205)

    def test_patterns_smallest_p_first_with_the_summary(self):
        out = results.pattern_verdict("")
        self.assertEqual([m["p"] for m in out["matches"]], [0.0002, 0.0499, 0.04996, 0.05, 0.2, 0.3, 0.6, 0.9])
        self.assertEqual(out["summary"], {"scope": "all funds", "tests": 8, "p_below_0.05": 3, "expected_by_luck": 0.4,
                                          "survive_false_discovery_check": 2,
                                          "note": "q-values correct for all 8 tests across the funds, whatever the scope"})
        self.assertEqual(out["more_matches"], 0)

    def test_summary_counts_only_the_asked_fund(self):
        summary = results.pattern_verdict("", "soxl")["summary"]
        self.assertEqual({k: summary[k] for k in ("scope", "tests", "p_below_0.05", "survive_false_discovery_check")},
                         {"scope": "SOXL", "tests": 5, "p_below_0.05": 2, "survive_false_discovery_check": 2})
        self.assertIn("all 8 tests", summary["note"])

    def test_patterns_by_query_and_fund(self):
        self.assertEqual([(m["fund"], m["pattern"]) for m in results.pattern_verdict("fomc")["matches"]],
                         [("DPST", "FOMC decision day"), ("SOXL", "Day after FOMC")])
        self.assertEqual([m["pattern"] for m in results.pattern_verdict("FOMC", fund="soxl")["matches"]], ["Day after FOMC"])
        self.assertEqual([m["family"] for m in results.pattern_verdict("signal")["matches"]], ["signal", "signal"])

    def test_unknown_pattern_suggests_queries(self):
        with self.assertRaisesRegex(ResultsError, "No pattern test matches 'moon'.*fed, last30, signal, week, weekday"):
            results.pattern_verdict("moon")
        with self.assertRaisesRegex(ResultsError, "on DPST"):
            results.pattern_verdict("Tue", fund="dpst")

    def test_long_lists_are_cut_and_counted(self):
        with mock.patch.object(results, "MAX_PATTERNS", 2):
            out = results.pattern_verdict("")
        self.assertEqual(len(out["matches"]), 2)
        self.assertEqual(out["more_matches"], 6)


def have_results():
    """True when the real results are there and from the current analyze.py."""
    try:
        results.load()
        return True
    except ResultsError:
        return False


NEEDS_RESULTS = "needs a current data/soxl-labu-dpst/results_5y.json (run fetch_prices.py, then analyze.py)"


@unittest.skipUnless(have_results(), NEEDS_RESULTS)
class RealResults(unittest.TestCase):
    """The answers agree with the README and with what analyze.py saved."""

    def test_readme_rsi2_rule(self):
        rules = {r["rule"]: r for r in results.get_results("SOXL")["rules"]}
        rsi2 = rules["RSI(2)<10 -> exit above 5-day avg or day 10"]
        self.assertEqual(round(rsi2["total_return_pct"]), 284)
        self.assertEqual(round(rsi2["max_drawdown_pct"]), -62)
        self.assertEqual(rsi2["years_up"], "5 of 5")

    def test_pattern_counts(self):
        out = results.pattern_verdict("")
        saved = results.load()["fdr"]
        self.assertEqual(out["summary"]["tests"], 189)
        self.assertEqual([out["summary"][k] for k in ("tests", "p_below_0.05", "expected_by_luck", "survive_false_discovery_check")],
                         [saved[k] for k in ("n_tests", "n_p_below_05", "expected_by_chance", "n_survive_q10")])  # same cutoffs as analyze.py
        self.assertEqual(len(out["matches"]) + out["more_matches"], 189)
        self.assertEqual((out["matches"][0]["fund"], out["matches"][0]["pattern"]), ("SOXL", "Up 6%+ at 3:30"))

    def test_every_rule_has_its_terms(self):
        import analyze
        cost = f"{analyze.COST * 100:g}% cost"
        for fund, data in results.load()["funds"].items():
            for name in data["backtests"]:
                with self.subTest(fund=fund, rule=name):
                    self.assertIn(name, results.TERMS, "add how this rule trades to results.TERMS")
                    terms = results.TERMS[name]
                    self.assertTrue(cost in terms or "no costs" in terms, terms)

    def test_every_field_is_explained(self):
        """analyze.py can't add a field the glossary doesn't explain, at any depth: the model would have to guess what it
        means. And every field the glossary explains is in the results (get_section checks the top level)."""
        labels = {"name", "day", "bucket", "vix", "at_330"}  # a row's own name, not a number

        def keys(value):
            if isinstance(value, dict):
                for k, v in value.items():
                    yield k
                    yield from keys(v)
            elif isinstance(value, list):
                for v in value:
                    yield from keys(v)

        for fund, data in results.load()["funds"].items():
            for section, glossary in results.SECTIONS.items():
                value = data[section]
                top = set(value) if isinstance(value, dict) else {"rows"}
                explained = {k for key in glossary for k in key.split(", ")}
                text = " ".join(glossary.values())
                with self.subTest(fund=fund, section=section):
                    self.assertLessEqual(top, explained, "explain it in results.SECTIONS")
                    nested = set(keys(value)) - top - explained - labels
                    self.assertEqual(sorted(k for k in nested if not re.search(rf"\b{re.escape(k)}\b", text)), [])
                    results.get_section(fund, section)  # raises if an explained field is missing

    def test_weekday_names(self):
        found = [m["pattern"] for m in results.pattern_verdict("Monday", "SOXL")["matches"]]
        self.assertLessEqual({"Mon", "Mon overnight gap", "Week low on Monday or Friday"}, set(found))


if __name__ == "__main__":
    unittest.main()
