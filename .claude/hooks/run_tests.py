"""Claude Code hook: run the tests after Claude edits the analysis, the studies or the tests.

Claude Code runs this after every Edit or Write (see .claude/settings.json) and passes the tool call
as JSON on stdin. If the edited file is under backtests/, studies/ or tests/, the unit tests run. When
they fail, the hook prints {"decision": "block", "reason": ...} with the failures, and Claude Code shows
that to Claude. The edit itself stays; Claude sees what broke and fixes it.

After an edit under backtests/, if the downloaded prices are here, it also runs check_reproducible.py
and tells Claude when the results or the chart no longer match: the README, the notes and the
thinkScript labels must then be updated (see CLAUDE.md). Edits anywhere else are ignored.
Uses only the Python standard library.
"""
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or pathlib.Path(__file__).resolve().parents[2]).resolve()
WATCHED = ("backtests", "studies", "tests")
RAW = ROOT / "data" / "soxl-labu-dpst" / "raw"
CHECK = ROOT / "backtests" / "soxl-labu-dpst" / "check_reproducible.py"
KEEP = 4000  # characters of test output passed to Claude (the end, where the failures and summary are)


def edited_file(event):
    """The file the Edit or Write touched, relative to the project, or None if it's outside it."""
    path = (event.get("tool_input") or {}).get("file_path") or (event.get("tool_response") or {}).get("filePath")
    if not path:
        return None
    try:
        return (ROOT / path).resolve().relative_to(ROOT)  # ROOT / an absolute path is just that path
    except ValueError:
        return None


def run(*args):
    p = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, timeout=90)
    return p.returncode, (p.stdout + p.stderr).strip()


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0  # not a tool call we understand; never get in the way
    rel = edited_file(event)
    if rel is None or not rel.parts or rel.parts[0] not in WATCHED:
        return 0
    code, out = run("-m", "unittest", "discover", "-s", "tests")
    if code:
        print(json.dumps({"decision": "block",
                          "reason": f"The unit tests fail after this edit to {rel.as_posix()}:\n\n{out[-KEEP:]}"}))
        return 0
    if rel.parts[0] == "backtests" and RAW.is_dir() and CHECK.exists():
        code, out = run(str(CHECK))
        if code:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": out}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
