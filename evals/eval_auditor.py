"""Eval for the numbers-auditor agent (.claude/agents/numbers-auditor.md): plant wrong numbers, see what it finds.

Copies README.md, notes/ and studies/ into a temporary folder, changes seven numbers there (PLANTED), and runs
three auditors at the same time, one each for the README, the notes and the thinkScript files. Each is
`claude -p --agent numbers-auditor`: read-only, with only this repo's MCP server. The three only read, so they
need no separate worktrees. A run passes when every planted number is reported as a mismatch, and nothing else.

With --clean, nothing is planted: the auditors check the real documents, which is the agent's actual job.
Needs the Claude Code CLI, signed in, the results from analyze.py and the .venv (see the README). A run takes
about a minute and roughly a dollar of usage.
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

from run_evals import PREFIX, ROOT, SERVER, mcp_config, preflight

AGENT = ROOT / ".claude" / "agents" / "numbers-auditor.md"
REPORTS = ROOT / "data" / "evals"
TIMEOUT = 600  # seconds per auditor
GROUPS = {
    "readme": ["README.md"],
    "notes": ["notes/soxl-labu-dpst-5yr-retest.md"],
    "studies": sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "studies" / "soxl-labu-dpst").glob("*.ts")),
}
# Each changes one true number into a plausible wrong one: swapped digits, a flipped sign, a nearby value.
PLANTED = [
    {"file": "README.md", "old": "**+284%**, −62%", "new": "**+248%**, −62%", "wrong": "248"},
    {"file": "README.md", "old": "+558%", "new": "+585%", "wrong": "585"},
    {"file": "notes/soxl-labu-dpst-5yr-retest.md", "old": "next day −0.61% on average", "new": "next day −0.16% on average", "wrong": "0.16"},
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
    """Make each planted change; return the line number it landed on, per plant."""
    lines = []
    for p in planted:
        path = pathlib.Path(folder) / p["file"]
        text = path.read_text()
        if text.count(p["old"]) != 1:
            raise ValueError(f"{p['file']}: {p['old']!r} should appear once, appears {text.count(p['old'])} times")
        text = text.replace(p["old"], p["new"])
        path.write_text(text)
        lines.append(text[:text.index(p["new"])].count("\n") + 1)
    return lines


def parse_report(text):
    """The agent's JSON report, from a ```json block or the outermost braces; None if there isn't one."""
    block = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S)
    candidates = [block.group(1)] if block else []
    if "{" in text and "}" in text:  # a reply cut off mid-JSON has no closing brace
        candidates.append(text[text.index("{"):text.rindex("}") + 1])
    for candidate in candidates:
        try:
            report = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(report, dict) and isinstance(report.get("mismatches"), list):
            return report
    return None


def same_file(a, b):
    return pathlib.PurePosixPath(str(a).replace("\\", "/")).as_posix().lstrip("./").endswith(pathlib.PurePosixPath(b).as_posix())


def catches(mismatch, plant, line):
    """A reported mismatch is this plant if it's in the same file, on its line (give or take one) or quoting its number."""
    if not same_file(mismatch.get("file", ""), plant["file"]):
        return False
    near = isinstance(mismatch.get("line"), int) and abs(mismatch["line"] - line) <= 1
    return near or plant["wrong"] in str(mismatch.get("written", ""))


def score(mismatches, planted, lines):
    caught = [any(catches(m, p, line) for m in mismatches) for p, line in zip(planted, lines)]
    extra = [m for m in mismatches if not any(catches(m, p, line) for p, line in zip(planted, lines))]
    return {"caught": sum(caught), "planted": len(planted), "missed": [p for p, c in zip(planted, caught) if not c], "extra": extra}


def audit(name, files, folder, config, model):
    """One auditor on one group of files: its report, tool calls and cost."""
    cmd = ["claude", "-p", "Audit the numbers in: " + ", ".join(files), "--agent", "numbers-auditor",
           "--mcp-config", str(config), "--strict-mcp-config", "--permission-mode", "dontAsk",
           "--allowedTools", f"Read Grep Glob mcp__{SERVER}", "--output-format", "stream-json", "--verbose",
           "--no-session-persistence"]
    if model:
        cmd += ["--model", model]
    run = {"group": name, "files": files, "tools": {}, "cost_usd": None, "seconds": None, "model": None, "report": None, "error": None}
    try:
        p = subprocess.run(cmd, cwd=folder, capture_output=True, text=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        run["error"] = f"timeout after {TIMEOUT} s"
        return run
    for line in p.stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            run["model"] = event.get("model")
        elif event.get("type") == "assistant":
            for b in event["message"]["content"]:
                if b.get("type") == "tool_use":
                    tool = b["name"].removeprefix(PREFIX)
                    run["tools"][tool] = run["tools"].get(tool, 0) + 1
        elif event.get("type") == "result":
            run["cost_usd"], run["seconds"] = event.get("total_cost_usd"), (event.get("duration_ms") or 0) / 1000
            run["report"] = parse_report(event.get("result") or "")
            if event.get("subtype") != "success" or run["report"] is None:
                run["error"] = event.get("subtype") if event.get("subtype") != "success" else "no JSON report in the answer"
    if p.returncode and not run["error"]:
        run["error"] = f"exit {p.returncode}: {p.stderr.strip()[:200]}"
    return run


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
    mismatches = [m for r in runs for m in (r["report"] or {}).get("mismatches", [])]
    result = score(mismatches, planted, lines)
    for r in runs:
        rep = r["report"] or {}
        cost = f"${r['cost_usd']:.2f}" if r["cost_usd"] is not None else "-"
        print(f"{r['group']:<8} {cost:>6} {r['seconds'] or 0:5.0f} s  {r['model']}  checked {rep.get('checked', '-')}, "
              f"mismatches {len(rep.get('mismatches', []))}, not found {len(rep.get('not_found', []))}, "
              f"not from results {rep.get('not_from_results', '-')}  tools {r['tools']}" + (f"  ERROR: {r['error']}" if r["error"] else ""))
    if planted:
        print(f"\nPlanted errors caught: {result['caught']} of {result['planted']}")
    for p in result["missed"]:
        print(f"  MISSED  {p['file']}: {p['new']!r} (was {p['old']!r})")
    for m in result["extra"]:
        print(f"  {'FLAGGED' if planted else 'MISMATCH'}  {m.get('file')}:{m.get('line')}  {m.get('written')} vs {m.get('actual')}  ({m.get('text', '')[:80]})")
    for r in runs:
        for nf in (r["report"] or {}).get("not_found", []):
            print(f"  not found  {nf.get('file')}:{nf.get('line')}  {nf.get('text', '')[:100]}")
    passed = not result["missed"] and not result["extra"] and not any(r["error"] for r in runs)
    total = sum(r["cost_usd"] or 0 for r in runs)
    print(f"\n{'PASS' if passed else 'FAIL'}: ${total:.2f} of API-equivalent usage")
    REPORTS.mkdir(parents=True, exist_ok=True)
    report = REPORTS / f"auditor-{'clean' if args.clean else 'planted'}-{dt.datetime.now():%Y%m%d-%H%M%S}.json"
    report.write_text(json.dumps({"model": args.model or "agent default", "clean": args.clean, "passed": passed,
                                  "score": {k: v for k, v in result.items() if k != "extra"}, "extra": result["extra"],
                                  "runs": runs}, indent=1))
    print(f"Report: {report.relative_to(ROOT)}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
