"""Check that the saved results and the README chart still come out of the code, byte for byte.

1. Copy the downloaded prices into a fresh temporary folder, run analyze.py there, and compare its
   results_5y.json with data/soxl-labu-dpst/results_5y.json.
2. Run make_chart.py there on the saved results and compare the SVG with docs/images/soxl-growth-5y.svg.
   The committed chart was drawn from the author's download. A separate download gives slightly
   different prices, so for anyone else this step can differ even when the code is unchanged.

The prices aren't in the repo, so this needs fetch_prices.py and analyze.py to have run first.
Exit code: 0 = both match, 1 = something differs, 2 = nothing to check yet (no prices or no saved
results), 3 = analyze.py or make_chart.py failed or ran too long.
Run it from anywhere:  python3 backtests/soxl-labu-dpst/check_reproducible.py
Uses only the Python standard library.
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TIMEOUT = float(os.environ.get("CHECK_REPRODUCIBLE_TIMEOUT", 25))  # seconds per script; tests lower it


class Failed(Exception):
    """analyze.py or make_chart.py crashed or ran past the timeout."""


def run(script, cwd):
    try:
        p = subprocess.run([sys.executable, str(HERE / script)], cwd=cwd, capture_output=True, text=True,
                           timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        raise Failed(f"{script} didn't finish within {TIMEOUT:g} s.") from None
    if p.returncode:
        raise Failed(f"{script} failed:\n{p.stderr}")


def same(a, b):
    return a.exists() and b.exists() and a.read_bytes() == b.read_bytes()


def check(raw, results, chart, chart_src):
    """The two comparisons, as a list of problems. Paths are relative to the repo root."""
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        shutil.copytree(ROOT / raw, tmp / raw)
        run("analyze.py", tmp)
        if not same(tmp / results, ROOT / results):
            problems.append(f"analyze.py gives different results from {results}. "
                            "If the change is intended: rerun analyze.py and make_chart.py, then update the numbers "
                            "in README.md, notes/ and the thinkScript labels.")
        (tmp / chart_src).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / results, tmp / chart_src)  # the chart is checked against the saved results
        (tmp / chart).parent.mkdir(parents=True, exist_ok=True)
        run("make_chart.py", tmp)
        if not same(tmp / chart, ROOT / chart):
            problems.append(f"make_chart.py draws a different chart from {chart}. "
                            "If the chart code changed on purpose: rerun make_chart.py and commit the new chart. "
                            "If only the prices differ (a separate download from the author's), leave the "
                            "committed chart as it is.")
    return problems


def main():
    try:
        import analyze  # the scripts' own paths, relative to the repo root
        import make_chart
    except Exception as e:  # a broken edit; the unit tests say more
        print(f"Can't import analyze.py or make_chart.py: {e!r}")
        return 3
    if not (ROOT / analyze.RAW).is_dir():
        print(f"No downloaded prices in {analyze.RAW}: run fetch_prices.py, then analyze.py.")
        return 2
    if not (ROOT / analyze.OUT).exists():
        print(f"No saved results in {analyze.OUT}: run analyze.py.")
        return 2
    try:
        problems = check(analyze.RAW, analyze.OUT, make_chart.OUT, make_chart.SRC)
    except Failed as e:
        print(e)
        return 3
    for p in problems:
        print("DIFFERS:", p)
    if not problems:
        print(f"Reproducible: {analyze.OUT} and {make_chart.OUT} match a fresh run.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
