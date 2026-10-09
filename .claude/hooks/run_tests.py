"""Claude Code hook: run the tests after Claude edits the analysis, the studies, the tests or this hook.

Claude Code runs this after every Edit or Write (see .claude/settings.json) and passes the tool call
as JSON on stdin. If the edited file is under backtests/, studies/, tests/ or .claude/, the unit tests
run. When they fail or hang, the hook prints {"decision": "block", "reason": ...}, and Claude Code shows
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
import tempfile

ROOT = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or pathlib.Path(__file__).resolve().parents[2]).resolve()
WATCHED = ("backtests", "studies", "tests", ".claude")
RAW = ROOT / "data" / "soxl-labu-dpst" / "raw"
CHECK = ROOT / "backtests" / "soxl-labu-dpst" / "check_reproducible.py"
# Time limits in seconds. Together they stay under the hook's 120 s timeout in .claude/settings.json.
TEST_TIMEOUT = int(os.environ.get("RUN_TESTS_TIMEOUT", 50))  # tests/test_hook.py lowers it
CHECK_TIMEOUT = 60
HEAD, TAIL = 2500, 1500  # characters of output passed to Claude: the first failures, then the summary


def field(event, key, name):
    """event[key][name] if it's a string, else None: Claude Code's input is never trusted to be well-formed."""
    part = event.get(key) if isinstance(event, dict) else None
    value = part.get(name) if isinstance(part, dict) else None
    return value if isinstance(value, str) else None


def edited_file(event):
    """The file the Edit or Write touched, relative to the project, or None if it's outside it."""
    path = field(event, "tool_input", "file_path") or field(event, "tool_response", "filePath")
    if not path:
        return None
    try:
        return (ROOT / path).resolve().relative_to(ROOT)  # ROOT / an absolute path is just that path
    except (ValueError, OSError):
        return None


def clip(text):
    """Long output loses its middle: the first failure is usually the cause, and the end has the summary."""
    if len(text) <= HEAD + TAIL:
        return text
    return f"{text[:HEAD]}\n\n[... {len(text) - HEAD - TAIL} characters cut ...]\n\n{text[-TAIL:]}"


def run(timeout, *args):
    """Run Python in the project; return (exit code, output), or (None, "") if it ran past the timeout."""
    # A fresh, empty bytecode cache for each run. Python reuses a cached .pyc when the source has the same
    # size and timestamp, so a quick same-length edit (0.5 -> 0.4) could otherwise test the old code.
    with tempfile.TemporaryDirectory() as cache:
        try:
            p = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout,
                               env=dict(os.environ, PYTHONPYCACHEPREFIX=cache))
        except subprocess.TimeoutExpired:
            return None, ""
    return p.returncode, (p.stdout + p.stderr).strip()


def block(reason):
    print(json.dumps({"decision": "block", "reason": reason}))


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0  # not a tool call we understand; never get in the way
    rel = edited_file(event)
    if rel is None or not rel.parts or rel.parts[0] not in WATCHED:
        return 0
    code, out = run(TEST_TIMEOUT, "-m", "unittest", "discover", "-s", "tests")
    if code is None:
        block(f"The unit tests didn't finish within {TEST_TIMEOUT} s after this edit to {rel.as_posix()}. "
              "Look for an endless loop.")
    elif code:
        block(f"The unit tests fail after this edit to {rel.as_posix()}:\n\n{clip(out)}")
    elif rel.parts[0] == "backtests" and RAW.is_dir() and CHECK.exists():
        code, out = run(CHECK_TIMEOUT, str(CHECK))
        if code:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": clip(out)}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
