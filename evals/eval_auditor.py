"""Eval for the numbers-auditor agent (.claude/agents/numbers-auditor.md): plant wrong numbers, see what it finds.

Copies README.md, notes/ and studies/ into a temporary folder, changes seven numbers there (PLANTED), and runs
three auditors at the same time, one each for the README, the notes and the files in studies/. Each is
`claude -p --agent numbers-auditor`: read-only, with only this repo's MCP server. The three only read, so they
need no separate worktrees. A run passes when every planted number is reported as a mismatch and nothing else
is, and each auditor connected to the server and checked a plausible share of its numbers (MIN_CHECKED).

With --clean, nothing is planted: the auditors check the real documents, which is the agent's actual job.
Needs the Claude Code CLI, signed in, the results from analyze.py and the .venv (see the README). On Sonnet, a
run takes under a minute and about 60 cents of usage.
Run from the repo root:  python3 evals/eval_auditor.py   (options: --clean, --model)
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

from run_evals import PREFIX, ROOT, SERVER, mcp_config, parse_stream, preflight

AGENT = ROOT / ".claude" / "agents" / "numbers-auditor.md"
REPORTS = ROOT / "data" / "evals"
TIMEOUT = 600  # seconds per auditor
GROUPS = {
    "readme": ["README.md"],
    "notes": ["notes/soxl-labu-dpst-5yr-retest.md"],
    "studies": sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "studies" / "soxl-labu-dpst").iterdir() if p.is_file()),
}
# An auditor that checks far fewer numbers than this didn't do its job, even if it reports no mismatches.
# Sonnet's runs check about 37-43 (README), 157-174 (notes) and 129 (.ts files, before README.txt joined them).
MIN_CHECKED = {"readme": 25, "notes": 110, "studies": 90}
# Each changes one true number into a plausible wrong one: swapped digits, a flipped sign, a nearby value.
# `wrong` is the planted number, with its sign, as an auditor would quote it.
PLANTED = [
    {"file": "README.md", "old": "**+284%**, −62%", "new": "**+248%**, −62%", "wrong": "248"},
    {"file": "README.md", "old": "+558%", "new": "+585%", "wrong": "585"},
    {"file": "notes/soxl-labu-dpst-5yr-retest.md", "old": "next day −0.61% on average", "new": "next day −0.16% on average", "wrong": "-0.16"},
    {"file": "notes/soxl-labu-dpst-5yr-retest.md", "old": "720 full days", "new": "702 full days", "wrong": "702"},
    {"file": "notes/soxl-labu-dpst-5yr-retest.md", "old": "| 2-sigma drop, hold 3 days | −49%", "new": "| 2-sigma drop, hold 3 days | +49%", "wrong": "+49"},
    {"file": "studies/soxl-labu-dpst/LEV3X_Dip_STUDY.ts", "old": "67 trades, 73% won", "new": "67 trades, 37% won", "wrong": "37"},
    {"file": "studies/soxl-labu-dpst/LEV3X_Intraday_STUDY.ts", "old": "averaged +0.75% and rose on 60% of days", "new": "averaged +0.75% and rose on 66% of days", "wrong": "66"},
]


def copy_project(folder):
    """The documents and the agent, in a folder of their own."""
    folder = pathlib.Path(folder)
    for path in ("README.md", "notes", "studies", ".claude/agents"):
        src, dst = ROOT / path, folder / path
        dst.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if src.is_dir() else shutil.copy2)(src, dst)


def plant(folder, planted=PLANTED):
    """Make each planted change; return the line number of each, where its old text was."""
    lines = []
    for p in planted:
        path = pathlib.Path(folder) / p["file"]
        text = path.read_text()
        if text.count(p["old"]) != 1:
            raise ValueError(f"{p['file']}: {p['old']!r} should appear once, appears {text.count(p['old'])} times")
        lines.append(text[:text.index(p["old"])].count("\n") + 1)
        path.write_text(text.replace(p["old"], p["new"]))
    return lines


def valid(report):
    """The agent's report has the shape the eval reads: lists of objects with the fields it uses."""
    if not isinstance(report, dict) or not isinstance(report.get("checked"), int):
        return False
    for key, fields in (("mismatches", ("file", "line", "written")), ("not_found", ("file", "line"))):
        entries = report.get(key)
        if not isinstance(entries, list) or not all(isinstance(e, dict) and all(f in e for f in fields) for e in entries):
            return False
    return True


def parse_report(text):
    """The agent's JSON report, from a ```json block or the outermost braces; None if there's no valid one."""
    block = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S)
    candidates = [block.group(1)] if block else []
    if "{" in text and "}" in text:  # a reply cut off mid-JSON has no closing brace
        candidates.append(text[text.index("{"):text.rindex("}") + 1])
    for candidate in candidates:
        try:
            report = json.loads(candidate)
        except ValueError:
            continue
        if valid(report):
            return report
    return None


def same_file(reported, planted):
    """Paths match from the file name back as far as both go: '/tmp/x/README.md' and 'LEV3X_Dip_STUDY.ts' match."""
    a = pathlib.PurePosixPath(str(reported).replace("\\", "/")).parts
    b = pathlib.PurePosixPath(planted).parts
    n = min(len(a), len(b))
    return n > 0 and a[-n:] == b[-n:]


def numbers(text):
    """The numbers in a quoted value, with their signs: '−0.16%' gives '-0.16', '+49%' gives '49'."""
    text = str(text).replace("−", "-").replace("–", "-")
    return {n.lstrip("+") for n in re.findall(r"[-+]?\d+(?:\.\d+)?", text)}


def evidence(mismatch, plant, line):
    """How a reported mismatch points at a plant in the same file: its line, and the number it quotes, sign included."""
    if not same_file(mismatch.get("file", ""), plant["file"]):
        return set()
    found = set()
    if mismatch.get("line") == line:
        found.add("line")
    if plant["wrong"].lstrip("+") in numbers(mismatch.get("written", "")):
        found.add("number")
    return found


def score(mismatches, planted, lines):
    """Each reported mismatch can catch one plant at most. The best evidence pairs first: line and number, then
    the number (line numbers can be off by one), then the line."""
    free = list(mismatches)
    caught = [False] * len(planted)
    for needed in ({"line", "number"}, {"number"}, {"line"}):
        for i, (p, line) in enumerate(zip(planted, lines)):
            if caught[i]:
                continue
            for m in free:
                if needed <= evidence(m, p, line):
                    caught[i] = True
                    free.remove(m)
                    break
    return {"caught": sum(caught), "planted": len(planted), "missed": [p for p, c in zip(planted, caught) if not c], "extra": free}


def audit(name, files, folder, config, model):
    """One auditor on one group of files: its report, tool calls, cost, and anything that went wrong."""
    cmd = ["claude", "-p", "Audit the numbers in: " + ", ".join(files), "--agent", "numbers-auditor",
           "--mcp-config", str(config), "--strict-mcp-config", "--permission-mode", "dontAsk",
           "--allowedTools", f"Read Grep Glob mcp__{SERVER}", "--output-format", "stream-json", "--verbose",
           "--no-session-persistence"]
    if model:
        cmd += ["--model", model]
    try:
        p = subprocess.run(cmd, cwd=folder, capture_output=True, text=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL)
        run = parse_stream(p.stdout.splitlines())
        if p.returncode and not run["error"]:
            run["error"] = f"exit {p.returncode}: {p.stderr.strip()[:200]}"
    except subprocess.TimeoutExpired:
        run = {"tools": [], "answer": "", "cost_usd": None, "error": f"timeout after {TIMEOUT} s", "server": None, "model": None, "seconds": None}
    run["report"] = parse_report(run["answer"])
    problems = [run["error"]] if run["error"] else []
    if run["server"] != "connected":
        problems.append(f"the MCP server was {run['server'] or 'not reported'}")
    if run["report"] is None:
        problems.append("no valid JSON report in the answer")
    elif run["report"]["checked"] < MIN_CHECKED.get(name, 1):
        problems.append(f"checked only {run['report']['checked']} numbers (expected at least {MIN_CHECKED.get(name, 1)})")
    counts = {}
    for t in run["tools"]:
        counts[t.removeprefix(PREFIX)] = counts.get(t.removeprefix(PREFIX), 0) + 1
    return {"group": name, "files": files, **run, "tools": counts, "problems": problems}


def summary(r):
    rep = r["report"] or {}
    cost = f"${r['cost_usd']:.2f}" if r["cost_usd"] is not None else "-"
    line = (f"{r['group']:<8} {cost:>6} {r['seconds'] or 0:5.0f} s  {r['model']}  checked {rep.get('checked', '-')}, "
            f"mismatches {len(rep.get('mismatches', []))}, not found {len(rep.get('not_found', []))}, "
            f"not from results {rep.get('not_from_results', '-')}  tools {r['tools']}")
    return line + "".join(f"\n         PROBLEM: {p}" for p in r["problems"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--clean", action="store_true", help="plant nothing: audit the real documents")
    parser.add_argument("--model", help="model for the auditors (default: the agent's, sonnet)")
    args = parser.parse_args(argv)
    problems = preflight()
    if not AGENT.exists():
        problems.append(f"{AGENT.relative_to(ROOT)} is missing.")
    if problems:
        sys.exit("Not running the eval:\n  " + "\n  ".join(problems))
    planted = [] if args.clean else PLANTED
    with tempfile.TemporaryDirectory() as folder:
        copy_project(folder)
        lines = plant(folder, planted)
        config = mcp_config(folder)
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(GROUPS)) as pool:
            runs = list(pool.map(lambda g: audit(g, GROUPS[g], folder, config, args.model), GROUPS))
    result = score([m for r in runs for m in (r["report"] or {}).get("mismatches", [])], planted, lines)
    passed = not result["missed"] and not result["extra"] and not any(r["problems"] for r in runs)
    REPORTS.mkdir(parents=True, exist_ok=True)  # saved before printing, so a paid run always leaves its report
    report = REPORTS / f"auditor-{'clean' if args.clean else 'planted'}-{dt.datetime.now():%Y%m%d-%H%M%S}.json"
    report.write_text(json.dumps({"model": args.model or "agent default", "clean": args.clean, "passed": passed,
                                  "score": {k: v for k, v in result.items() if k != "extra"}, "extra": result["extra"],
                                  "runs": runs}, indent=1))
    for r in runs:
        print(summary(r))
    if planted:
        print(f"\nPlanted errors caught: {result['caught']} of {result['planted']}")
    for p in result["missed"]:
        print(f"  MISSED  {p['file']}: {p['new']!r} (was {p['old']!r})")
    for m in result["extra"]:
        print(f"  {'FLAGGED' if planted else 'MISMATCH'}  {m.get('file')}:{m.get('line')}  {m.get('written')} vs {m.get('actual')}"
              f"  ({str(m.get('text') or '')[:80]})")
    for r in runs:
        for nf in (r["report"] or {}).get("not_found", []):
            print(f"  not found  {nf.get('file')}:{nf.get('line')}  {str(nf.get('text') or '')[:100]}")
    total = sum(r["cost_usd"] or 0 for r in runs)
    print(f"\n{'PASS' if passed else 'FAIL'}: ${total:.2f} of API-equivalent usage")
    print(f"Report: {report.relative_to(ROOT)}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
