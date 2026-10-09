"""Answers from the 5-year retest results, for the MCP server in server.py.

Each function reads data/soxl-labu-dpst/results_5y.json (written by analyze.py) on every call, so a rerun
of the analysis shows up without restarting the server (reading it takes about 5 ms), and returns plain
dicts, ready to send as JSON. Returns are percent. A question the results can't answer raises
ResultsError, with a message written for whoever asked: a person or a model.
Uses only the Python standard library.
"""
import json
import os
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS = pathlib.Path(os.environ.get("LETF_RESULTS") or ROOT / "data" / "soxl-labu-dpst" / "results_5y.json")
P_CUTOFF, Q_CUTOFF = 0.05, 0.10  # the study's thresholds: p for one test, q after the false-discovery check
MAX_PATTERNS = 25  # matches returned by pattern_verdict; the rest are counted
IGNORED_WORDS = {"a", "an", "and", "the", "of", "on", "for", "in", "rule", "rules", "strategy", "pattern", "patterns",
                 "effect", "effects", "test", "tests"}
RERUN = "From the repo root, run python3 backtests/soxl-labu-dpst/fetch_prices.py, then analyze.py."

# How each rule in analyze.py's backtests() trades. Most buy and sell at the close; these don't.
# tests/test_mcp_tools.py fails if the results have a rule that isn't here, so a new rule gets its terms.
AT_THE_CLOSE = "buys and sells at the close, 0.05% cost per side"
DAILY = "holds {} every day, a round trip each day (not counted as trades), {}"
TERMS = {
    "Buy & hold": "buys at the close before the window and holds to the end, 0.05% cost on the purchase",
    "RSI(2)<10 -> exit above 5-day avg": AT_THE_CLOSE,
    "RSI(2)<10 -> exit above 5-day avg or day 10": AT_THE_CLOSE,
    "Down >=2-sigma day -> hold 3 days": AT_THE_CLOSE,
    "3 down days -> exit first up day": AT_THE_CLOSE,
    "Close below lower Bollinger -> exit above 20-day avg": AT_THE_CLOSE,
    "Tuesday close -> Wednesday close": AT_THE_CLOSE,
    "FOMC-day close -> next close": AT_THE_CLOSE,
    "Overnight only (close->open)": DAILY.format("from the close to the next open", "0.05% cost per side"),
    "Intraday only (open->close)": DAILY.format("from the open to the close", "0.05% cost per side"),
    "Overnight only, before costs": DAILY.format("from the close to the next open", "no costs"),
    "Intraday only, before costs": DAILY.format("from the open to the close", "no costs"),
    "Tuesday close -> Wednesday open": "buys at Tuesday's close and sells at Wednesday's open, 0.05% cost per side",
}


class ResultsError(ValueError):
    """A question the results can't answer: no usable results, or an unknown fund, rule or pattern."""


def load():
    if not RESULTS.exists():
        raise ResultsError(f"No results file at {RESULTS}. {RERUN}")
    try:
        data = json.loads(RESULTS.read_text())
    except ValueError:
        raise ResultsError(f"Can't read {RESULTS}; it may be half-written. {RERUN}") from None
    usable = (isinstance(data, dict) and isinstance(data.get("funds"), dict) and data["funds"]
              and all("backtests" in f for f in data["funds"].values()) and "tests" in data.get("fdr", {}))
    if not usable:
        raise ResultsError(f"{RESULTS} is incomplete or from an older analyze.py. {RERUN}")
    return data


def fund_name(data, fund):
    name = str(fund).strip().upper()
    if name not in data["funds"]:
        raise ResultsError(f"Unknown fund {fund!r}. The retest covers {', '.join(data['funds'])} only.")
    return name


def words(text):
    return re.findall(r"[a-z0-9]+", str(text).lower())


def meaningful(query):
    return [w for w in words(query) if w not in IGNORED_WORDS]


def same_word(asked, have):
    """'boll' finds 'bollinger', and 'monday' finds 'mon' (the names shorten some words)."""
    return have.startswith(asked) or (len(have) >= 3 and asked.startswith(have))


def matches(query, text, in_order=False):
    """True if every word of the query matches a word of the text. in_order: one after another, as asked."""
    want, have = meaningful(query), words(text)
    if not in_order:
        return all(any(same_word(w, h) for h in have) for w in want)
    return any(all(same_word(w, h) for h, w in zip(have[i:], want)) for i in range(len(have) - len(want) + 1))


def search(query, items, text):
    """Every item whose text matches the query, those with the words in the asked order first:
    '3 down days' lists '3 down days -> exit first up day' before 'Down >=2-sigma day -> hold 3 days'."""
    found = [item for item in items if matches(query, text(item))]
    return sorted(found, key=lambda item: not matches(query, text(item), in_order=True))


def window(data):
    return {"start": data["window"][0], "end": data["window"][1]}


def rule_summary(name, bt):
    if bt is None:
        return None
    years = bt["years"]
    daily = TERMS.get(name, "").startswith("holds")
    return {
        "how_it_trades": TERMS.get(name, "not recorded"),
        "total_return_pct": bt["total"],
        "cagr_pct": bt["cagr"],
        "max_drawdown_pct": bt["max_dd"],
        "yearly_returns_pct": years,
        "years_up": f"{sum(y is not None and y > 0 for y in years)} of {len(years)}",
        "trades": None if daily else bt["trades"],
        "win_rate_pct": bt["win_rate"],
        "avg_trade_pct": bt["avg_trade"],
        "exposure_pct": bt["exposure"],
        "open_at_end": {"entered": bt["open_trade"][0], "return_pct": bt["open_trade"][1]} if bt["open_trade"] else None,
    }


def get_results(fund):
    """Every trading rule on one fund, best total return first."""
    data = load()
    fund = fund_name(data, fund)
    rules = data["funds"][fund]["backtests"]
    ranked = sorted(rules, key=lambda name: rules[name]["total"], reverse=True)
    return {"fund": fund, "window": window(data), "rules": [{"rule": name, **rule_summary(name, rules[name])} for name in ranked]}


def compare_funds(rule):
    """Every rule whose name matches, on each fund side by side (None where a fund lacks the rule)."""
    data = load()
    names = list(dict.fromkeys(name for f in data["funds"].values() for name in f["backtests"]))
    found = search(rule, names, str) if meaningful(rule) else []
    if not found:
        raise ResultsError(f"No rule matches {rule!r}. The rules are: " + "; ".join(names) + ".")
    return {"window": window(data),
            "rules": [{"rule": name, "funds": {f: rule_summary(name, d["backtests"].get(name)) for f, d in data["funds"].items()}}
                      for name in found]}


def verdict(p, q):
    if q < Q_CUTOFF:
        return "held up: survives the false-discovery check (q < 0.10)"
    if p < P_CUTOFF:
        return "probably luck: p < 0.05 on its own, but not after correcting for all the tests"
    return "no evidence: p >= 0.05"


def shown(x, cutoff):
    """x to 3 significant digits, or more if rounding would put it on the other side of the cutoff
    (0.0996 must not show as 0.1 next to "q < 0.10")."""
    for digits in range(3, 16):
        r = float(f"{x:.{digits}g}")
        if (r < cutoff) == (x < cutoff):
            return r
    return x


def pattern_verdict(query="", fund=None):
    """The pattern tests whose name matches `query` (all of them if it's empty), smallest p first."""
    data = load()
    every = data["fdr"]["tests"]
    scope = fund_name(data, fund) if fund else None
    tests = [t for t in every if t[0] == scope] if scope else every
    found = sorted(search(query, tests, lambda t: f"{t[1]} {t[2]}"), key=lambda t: t[3])
    if not found:
        families = sorted({t[1] for t in every})
        raise ResultsError(f"No pattern test matches {query!r}{' on ' + scope if scope else ''}. "
                           f"The test families are: {', '.join(families)}. Try a shorter query, such as "
                           "'RSI(2) below 10', 'FOMC', 'Tuesday', 'VIX 30' or 'gap up'.")
    return {
        "summary": {
            "scope": scope or "all funds",
            "tests": len(tests),
            "p_below_0.05": sum(t[3] < P_CUTOFF for t in tests),
            "expected_by_luck": round(P_CUTOFF * len(tests), 1),
            "survive_false_discovery_check": sum(t[4] < Q_CUTOFF for t in tests),
            "note": f"q-values correct for all {len(every)} tests across the funds, whatever the scope",
        },
        "matches": [{"fund": f, "family": family, "pattern": name, "p": shown(p, P_CUTOFF), "q": shown(q, Q_CUTOFF),
                     "verdict": verdict(p, q)} for f, family, name, p, q in found[:MAX_PATTERNS]],
        "more_matches": max(0, len(found) - MAX_PATTERNS),
    }
