"""Mini eval for the MCP server: ask Claude questions with known answers, using only this server's tools.

Each case runs `claude -p` from an empty temporary folder (no README or CLAUDE.md to read), with Claude
Code's built-in tools turned off and only the server from .mcp.json loaded and pre-approved. A case
passes when the answer contains the expected numbers or words, has none of the rejected ones (such as an
invented figure), and Claude called one of the expected tools. Claude Code also loads your user-level settings (and any global CLAUDE.md), so run this in a
plain setup.

Needs the Claude Code CLI, signed in, the results from analyze.py and the .venv from requirements.txt.
Each case is a real request: about 10 seconds, and a few US cents of usage.
Run from the repo root:  python3 evals/run_evals.py   (options: --model, --only, --jobs)
The report is saved to data/evals/. Uses only the Python standard library.
"""
import argparse
import concurrent.futures
import datetime as dt
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = "leveraged-etf-retest"
PREFIX = f"mcp__{SERVER}__"
REPORTS = ROOT / "data" / "evals"
TIMEOUT = 180  # seconds per case

# Expected answers are the published numbers (README.md, notes/), matched loosely: "+283.7%" or "284%".
CASES = [
    {"id": "rsi2-soxl",
     "ask": "What was the 5-year total return of SOXL's RSI(2) dip rule (buy when RSI(2) is under 10, sell on a "
            "close above the 5-day average or on day 10), and how many of the five years were up?",
     "expect": [r"\b28(3\.7|4)\s*%", r"\b5 of 5\b|all (five|5)"], "tools": ["get_results", "compare_funds"]},
    {"id": "labu-buy-and-hold",
     "ask": "How did simply buying and holding LABU do over the five years, and what was its worst drawdown?",
     # A loss can be written "-76.8%" or "lost 76.8%"; "gained 76.8%" must fail.
     "expect": [r"(-\s?|\b(lost|down|fell|loss of)\s)7(6\.8|7)\s*%", r"(-\s?|drawdown\D{0,12})97(\.1)?\s*%"],
     "tools": ["get_results", "compare_funds"]},
    {"id": "three-down-days",
     "ask": "Compare the '3 down days in a row, sell on the first up day' rule across SOXL, LABU and DPST.",
     "expect": [r"\b22(5\.5|6)\s*%", r"\+\s?9(\.4)?\s*%|\b9\.4\s*%", r"-\s?76(\.3)?\s*%"], "tools": ["compare_funds", "get_results"]},
    {"id": "best-rule-soxl",
     "ask": "Which trading rule had the highest 5-year total return on SOXL, and what was it?",
     "expect": [r"bollinger", r"\b55[78](\.9)?\s*%"], "tools": ["get_results"]},
    {"id": "what-held-up",
     "ask": "Of all the patterns tested, which held up after the false-discovery check?",
     "expect": [r"soxl", r"6\s*%.{0,40}3:30|3:30.{0,40}6\s*%"], "tools": ["pattern_verdict"]},
    {"id": "how-many-tests",
     "ask": "How many pattern tests were run, how many had p below 0.05, and how many would luck alone produce?",
     # The 6 must sit near "p below 0.05", and not be part of "6%+" or a date such as "Oct 6,".
     "expect": [r"\b189\b", r"\b9\.5\b",
                r"\b(6|six)\b(?![%+.,:\d]).{0,60}(0?\.05|p\s*<|below|under)|(0?\.05|p\s*<).{0,60}\b(6|six)\b(?![%+.,:\d])"],
     "tools": ["pattern_verdict"]},
    {"id": "fomc-soxl",
     "ask": "Is there a real FOMC-day effect on SOXL? Give the p-value.",
     "expect": [r"\b0?\.08\b|\b0?\.080\d?\b", r"no (real |reliable |statistical |significant )*(evidence|effect)|not (statistically )?significant|"
                                               r"isn'?t (real|significant)|not real|doesn'?t hold"], "tools": ["pattern_verdict"]},
    {"id": "unknown-fund",
     "ask": "What did the RSI(2) dip rule return on TQQQ?",
     "expect": [r"tqqq", r"\b(only|just) (covers?|tested|includes?|three)|not (covered|included|part of|tested)|"
                        r"(wasn'?t|isn'?t|was never|never) (covered|included|tested|part)|doesn'?t (cover|include)|no tqqq"],
     "reject": [r"tqqq[^.\n|]{0,40}[-+]?\d+(\.\d+)?\s*%"],  # a figure right after TQQQ is an invented one
     "tools": ["get_results", "compare_funds"]},
]


def normalize(text):
    """The answer as plain text: minus signs and dashes as '-', no markdown bold, lowercase."""
    return text.replace("−", "-").replace("–", "-").replace("**", "").lower()


def parse_stream(lines):
    """What happened in one `claude -p --output-format stream-json` run."""
    run = {"tools": [], "answer": "", "cost_usd": None, "error": None, "server": None}
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            run["server"] = next((s["status"] for s in event.get("mcp_servers", []) if s.get("name") == SERVER), "missing")
        elif kind == "assistant":
            run["tools"] += [b["name"] for b in event["message"]["content"] if b.get("type") == "tool_use"]
        elif kind == "result":
            run["answer"] = event.get("result") or ""
            run["cost_usd"] = event.get("total_cost_usd")
            if event.get("is_error") or event.get("subtype") != "success":
                run["error"] = event.get("subtype") or "error"
    return run


def grade(case, run):
    """The reasons a case failed; empty if it passed."""
    problems = []
    if run["error"]:
        problems.append(f"the run ended with {run['error']}")
    if run["server"] != "connected":
        problems.append(f"the MCP server was {run['server'] or 'not reported'}")
    used = [t.removeprefix(PREFIX) for t in run["tools"]]
    if not set(used) & set(case["tools"]):
        problems.append(f"expected a call to {' or '.join(case['tools'])}, got {used or 'none'}")
    answer = normalize(run["answer"])
    problems += [f"answer lacks /{pattern}/" for pattern in case["expect"] if not re.search(pattern, answer)]
    problems += [f"answer has /{pattern}/" for pattern in case.get("reject", []) if re.search(pattern, answer)]
    return problems


def preflight():
    """Why the eval can't run, found before any request is paid for: an empty list when it can."""
    problems = []
    if not shutil.which("claude"):
        problems.append("The claude CLI isn't on PATH.")
    command = json.loads((ROOT / ".mcp.json").read_text())["mcpServers"][SERVER]["command"]
    if not (ROOT / command).exists():
        problems.append(f"{command} is missing: create .venv and install requirements.txt (see the README).")
    sys.path.insert(0, str(ROOT / "mcp_server"))
    import results
    try:
        results.load()
    except results.ResultsError as e:
        problems.append(str(e))
    return problems


def mcp_config(folder):
    """.mcp.json with its paths made absolute, because the cases run from an empty folder."""
    config = json.loads((ROOT / ".mcp.json").read_text())
    server = config["mcpServers"][SERVER]
    server["command"] = str(ROOT / server["command"])
    server["args"] = [str(ROOT / a) if (ROOT / a).exists() else a for a in server["args"]]
    path = pathlib.Path(folder) / "mcp.json"
    path.write_text(json.dumps(config))
    return path


def run_case(case, config, model):
    cmd = ["claude", "-p", case["ask"], "--mcp-config", str(config), "--strict-mcp-config", "--tools", "",
           "--allowedTools", f"mcp__{SERVER}", "--permission-mode", "dontAsk",
           "--output-format", "stream-json", "--verbose", "--no-session-persistence"]
    if model:
        cmd += ["--model", model]
    with tempfile.TemporaryDirectory() as empty:
        try:
            p = subprocess.run(cmd, cwd=empty, capture_output=True, text=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL)
            run = parse_stream(p.stdout.splitlines())
            if p.returncode and not run["error"]:
                run["error"] = f"exit {p.returncode}: {p.stderr.strip()[:200]}"
        except subprocess.TimeoutExpired:
            run = {"tools": [], "answer": "", "cost_usd": None, "error": f"timeout after {TIMEOUT} s", "server": None}
    return {"id": case["id"], "ask": case["ask"], **run, "problems": grade(case, run)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--model", help="model alias or name for claude -p (default: Claude Code's)")
    parser.add_argument("--only", nargs="+", metavar="ID", help="run only these case ids")
    parser.add_argument("--jobs", type=int, default=4, help="cases run at the same time (default 4)")
    args = parser.parse_args(argv)
    cases = [c for c in CASES if not args.only or c["id"] in args.only]
    if not cases:
        sys.exit(f"No case matches {args.only}. The ids are: {', '.join(c['id'] for c in CASES)}")
    problems = preflight()
    if problems:
        sys.exit("Not running the eval:\n  " + "\n  ".join(problems))
    with tempfile.TemporaryDirectory() as folder:
        config = mcp_config(folder)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            runs = list(pool.map(lambda c: run_case(c, config, args.model), cases))
    for r in runs:
        status = "PASS" if not r["problems"] else "FAIL"
        cost = f"${r['cost_usd']:.3f}" if r["cost_usd"] is not None else "-"
        print(f"{status}  {r['id']:<18} {cost:>7}  tools: {', '.join(t.removeprefix(PREFIX) for t in r['tools']) or 'none'}")
        for problem in r["problems"]:
            print(f"      {problem}")
    passed = sum(not r["problems"] for r in runs)
    total_cost = sum(r["cost_usd"] or 0 for r in runs)
    print(f"\n{passed} of {len(runs)} passed, ${total_cost:.2f} of API-equivalent usage")
    REPORTS.mkdir(parents=True, exist_ok=True)
    report = REPORTS / f"eval-{dt.datetime.now():%Y%m%d-%H%M%S}.json"
    report.write_text(json.dumps({"model": args.model or "default", "passed": passed, "total": len(runs), "runs": runs}, indent=1))
    print(f"Report: {report.relative_to(ROOT)}")
    return 0 if passed == len(runs) else 1


if __name__ == "__main__":
    sys.exit(main())
