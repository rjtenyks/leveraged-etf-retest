"""Answers from the 5-year retest results, for the MCP server in server.py.

Each function reads data/soxl-labu-dpst/results_5y.json (written by analyze.py) on every call, so a rerun
of the analysis shows up without restarting the server, and returns plain dicts, ready to send as JSON.
Returns are percent. A question the results can't answer raises ResultsError, with a message written
for whoever asked: a person or a model.
Uses only the Python standard library.
"""
import json
import os
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS = pathlib.Path(os.environ.get("LETF_RESULTS") or ROOT / "data" / "soxl-labu-dpst" / "results_5y.json")
FUNDS = ("SOXL", "LABU", "DPST")
P_CUTOFF, Q_CUTOFF = 0.05, 0.10  # the study's thresholds: p for one test, q after the false-discovery check
MAX_PATTERNS = 25  # matches returned by pattern_verdict; the rest are counted
IGNORED_WORDS = {"a", "an", "and", "the", "of", "on", "for", "in", "rule", "strategy", "pattern"}


class ResultsError(ValueError):
    """A question the results can't answer: no results yet, or an unknown fund, rule or pattern."""


def load():
    if not RESULTS.exists():
        raise ResultsError(f"No results file at {RESULTS}. From the repo root, run "
                           "python3 backtests/soxl-labu-dpst/fetch_prices.py, then analyze.py.")
    return json.loads(RESULTS.read_text())


def fund_name(fund):
    name = str(fund).strip().upper()
    if name not in FUNDS:
        raise ResultsError(f"Unknown fund {fund!r}. The retest covers {', '.join(FUNDS)} only.")
    return name


def words(text):
    return re.findall(r"[a-z0-9]+", str(text).lower())


def meaningful(query):
    return [w for w in words(query) if w not in IGNORED_WORDS]


def matches(query, text, in_order=False):
    """True if every word of the query starts a word of the text: 'boll' finds 'Bollinger', 'rsi 2' finds 'RSI(2)<10'.
    in_order: the words must also come one after another, as in the query."""
    want, have = meaningful(query), words(text)
    if not in_order:
        return all(any(h.startswith(w) for h in have) for w in want)
    return any(all(h.startswith(w) for h, w in zip(have[i:], want)) for i in range(len(have) - len(want) + 1))


def search(query, items, text):
    """The items whose text matches the query, keeping only in-order matches if there are any:
    '3 down days' finds '3 down days -> exit first up day', not 'Down >=2-sigma day -> hold 3 days'."""
    found = [item for item in items if matches(query, text(item))]
    in_order = [item for item in found if matches(query, text(item), in_order=True)]
    return in_order or found


def window(data):
    return {"start": data["window"][0], "end": data["window"][1]}


def rule_summary(bt):
    years = bt["years"]
    return {
        "total_return_pct": bt["total"],
        "cagr_pct": bt["cagr"],
        "max_drawdown_pct": bt["max_dd"],
        "yearly_returns_pct": years,
        "years_up": f"{sum(y is not None and y > 0 for y in years)} of {len(years)}",
        "trades": bt["trades"],
        "win_rate_pct": bt["win_rate"],
        "avg_trade_pct": bt["avg_trade"],
        "exposure_pct": bt["exposure"],
        "open_at_end": {"entered": bt["open_trade"][0], "return_pct": bt["open_trade"][1]} if bt["open_trade"] else None,
    }


def get_results(fund):
    """Every trading rule on one fund, best total return first."""
    data, fund = load(), fund_name(fund)
    rules = data["funds"][fund]["backtests"]
    ranked = sorted(rules, key=lambda name: rules[name]["total"], reverse=True)
    return {"fund": fund, "window": window(data), "costs": "0.05% per side, trades at the close",
            "rules": [{"rule": name, **rule_summary(rules[name])} for name in ranked]}


def compare_funds(rule):
    """One rule (or every rule whose name matches) on all three funds, side by side."""
    data = load()
    names = list(data["funds"][FUNDS[0]]["backtests"])
    found = search(rule, names, str)
    if not found or not meaningful(rule):
        raise ResultsError(f"No rule matches {rule!r}. The rules are: " + "; ".join(names) + ".")
    return {"window": window(data), "costs": "0.05% per side, trades at the close",
            "rules": [{"rule": name, "funds": {f: rule_summary(data["funds"][f]["backtests"][name]) for f in FUNDS}}
                      for name in found]}


def verdict(p, q):
    if q < Q_CUTOFF:
        return "held up: survives the false-discovery check (q < 0.10)"
    if p < P_CUTOFF:
        return "probably luck: p < 0.05 on its own, but not after correcting for all the tests"
    return "no evidence: p >= 0.05"


def pattern_verdict(query="", fund=None):
    """The pattern tests whose name matches `query` (all of them if it's empty), smallest p first."""
    data = load()
    fdr = data["fdr"]
    tests = fdr["tests"]
    if fund:
        fund = fund_name(fund)
        tests = [t for t in tests if t[0] == fund]
    found = sorted(search(query, tests, lambda t: f"{t[1]} {t[2]}"), key=lambda t: t[3])
    if not found:
        families = sorted({t[1] for t in fdr["tests"]})
        raise ResultsError(f"No pattern test matches {query!r}{' on ' + fund if fund else ''}. "
                           f"The test families are: {', '.join(families)}. Try a shorter query, such as "
                           "'RSI(2) below 10', 'FOMC', 'Tue', 'VIX 30' or 'gap up'.")
    return {
        "summary": {"tests": fdr["n_tests"], "p_below_0.05": fdr["n_p_below_05"],
                    "expected_by_luck": fdr["expected_by_chance"], "survive_false_discovery_check": fdr["n_survive_q10"]},
        "matches": [{"fund": f, "family": family, "pattern": name, "p": round(p, 4), "q": round(q, 3), "verdict": verdict(p, q)}
                    for f, family, name, p, q in found[:MAX_PATTERNS]],
        "more_matches": max(0, len(found) - MAX_PATTERNS),
    }
