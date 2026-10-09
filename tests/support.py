"""Shared paths for the tests. Run the tests from the repo root:  python3 -m unittest discover -s tests

Importing this module puts the backtest scripts and the MCP server on sys.path, so a test can
`import analyze` or `import results`.
The folder name has a hyphen, so it can't be imported as a package.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "backtests" / "soxl-labu-dpst"
STUDIES = ROOT / "studies" / "soxl-labu-dpst"
MCP_SERVER = ROOT / "mcp_server"
FIXTURES = ROOT / "tests" / "fixtures"

for folder in (SCRIPTS, MCP_SERVER):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
