"""Shared helpers for the tests. Run the tests from the repo root:  python3 -m unittest discover -s tests"""
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "backtests" / "soxl-labu-dpst"
STUDIES = ROOT / "studies" / "soxl-labu-dpst"
FIXTURES = ROOT / "tests" / "fixtures"


def load_script(name):
    """Import a backtest script by file name. The folder name has a hyphen, so a plain import can't reach it."""
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
