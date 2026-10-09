"""Claude Code hook: run the tests after Claude edits the analysis, the studies, the tests or this hook.

Claude Code runs this after every Edit or Write (see .claude/settings.json) and passes the tool call
as JSON on stdin. If the edited file is under backtests/, studies/, tests/, mcp_server/, evals/ or
.claude/, the unit tests run, with the project's .venv Python when there is one, so the MCP server tests
run too. When they fail or hang, the hook prints {"decision": "block", "reason": ...}, and Claude Code
shows that to Claude. The edit itself stays; Claude sees what broke and fixes it.

After an edit under backtests/, it also runs check_reproducible.py, which needs the downloaded prices
and saved results (it skips without them). If the full analysis crashes or hangs, that blocks too. If
the results or the chart no longer match, Claude is told: the README, the notes and the thinkScript
labels must then be updated (see CLAUDE.md). Edits anywhere else are ignored.
Uses only the Python standard library.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or pathlib.Path(__file__).resolve().parents[2]).resolve()
WATCHED = ("backtests", "studies", "tests", "mcp_server", "evals", ".claude")
CHECK = ROOT / "backtests" / "soxl-labu-dpst" / "check_reproducible.py"
# Time limits in seconds. Together they stay under the hook's 120 s timeout in .claude/settings.json.
TEST_TIMEOUT = float(os.environ.get("RUN_TESTS_TIMEOUT", 50))  # tests/test_hook.py lowers it
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


def clear_bytecode():
    """Delete the project's cached bytecode. Python reuses a cached .pyc when the source has the same size
    and timestamp, so a quick same-length edit (0.5 -> 0.4) could otherwise test the old code. The standard
    library's cache stays, which keeps each run fast."""
    for folder in WATCHED:
        for cache in (ROOT / folder).glob("**/__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)


def python():
    """The project's .venv Python if there is one (it has the mcp package), else the one running this hook."""
    for venv in (ROOT / ".venv" / "bin" / "python", ROOT / ".venv" / "Scripts" / "python.exe"):
        if venv.exists():
            return str(venv)
    return sys.executable


def run(timeout, *args):
    """Run Python in the project; return (exit code, output), or (None, "") if it ran past the timeout."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPYCACHEPREFIX"}  # keep bytecode in __pycache__
    try:
        p = subprocess.run([python(), *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout, env=env)
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
    clear_bytecode()
    code, out = run(TEST_TIMEOUT, "-m", "unittest", "discover", "-s", "tests")
    if code is None:
        block(f"The unit tests didn't finish within {TEST_TIMEOUT:g} s after this edit to {rel.as_posix()}. "
              "Look for an endless loop.")
    elif code:
        block(f"The unit tests fail after this edit to {rel.as_posix()}:\n\n{clip(out)}")
    elif rel.parts[0] == "backtests" and CHECK.exists():
        code, out = run(CHECK_TIMEOUT, str(CHECK))  # exit 0 = reproducible, 2 = no prices to check against
        if code is None or code == 3:
            out = out or f"check_reproducible.py didn't finish within {CHECK_TIMEOUT:g} s."
            block(f"The unit tests pass, but the full analysis fails after this edit to {rel.as_posix()}:\n\n{clip(out)}")
        elif code == 1:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": clip(out)}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
