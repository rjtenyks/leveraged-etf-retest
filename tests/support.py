"""Shared paths for the tests. Run the tests from the repo root:  python3 -m unittest discover -s tests

Importing this module puts the backtest scripts on sys.path, so a test can `import analyze`.
The folder name has a hyphen, so it can't be imported as a package.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "backtests" / "soxl-labu-dpst"
STUDIES = ROOT / "studies" / "soxl-labu-dpst"
FIXTURES = ROOT / "tests" / "fixtures"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
