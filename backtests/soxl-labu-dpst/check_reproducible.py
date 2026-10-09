"""Check that the saved results and the README chart still come out of the code, byte for byte.

1. Copy the downloaded prices into a fresh temporary folder, run analyze.py there, and compare its
   results_5y.json with data/soxl-labu-dpst/results_5y.json.
2. Run make_chart.py there on the saved results and compare the SVG with docs/images/soxl-growth-5y.svg.

The prices aren't in the repo, so this needs fetch_prices.py and analyze.py to have run first.
Exit code: 0 = both match, 1 = something differs, 2 = no downloaded prices.
Run from the repo root:  python3 backtests/soxl-labu-dpst/check_reproducible.py
Uses only the Python standard library.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
RAW = pathlib.Path("data/soxl-labu-dpst/raw")
RESULTS = pathlib.Path("data/soxl-labu-dpst/results_5y.json")
CHART = pathlib.Path("docs/images/soxl-growth-5y.svg")


def run(script, cwd):
    p = subprocess.run([sys.executable, str(HERE / script)], cwd=cwd, capture_output=True, text=True)
    if p.returncode:
        sys.exit(f"{script} failed:\n{p.stderr}")


def same(a, b):
    return a.exists() and b.exists() and a.read_bytes() == b.read_bytes()


def main():
    if not RAW.is_dir() or not RESULTS.exists():
        print(f"No downloaded prices in {RAW.parent}: run fetch_prices.py and analyze.py first.")
        return 2
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        shutil.copytree(RAW, tmp / RAW)
        run("analyze.py", tmp)
        if not same(tmp / RESULTS, RESULTS):
            problems.append(f"analyze.py gives different results from {RESULTS}. "
                            "If the change is intended: rerun analyze.py and make_chart.py, then update the numbers "
                            "in README.md, notes/ and the thinkScript labels.")
        shutil.copy(RESULTS, tmp / RESULTS)  # the chart is checked against the saved results
        (tmp / CHART.parent).mkdir(parents=True)
        run("make_chart.py", tmp)
        if not same(tmp / CHART, CHART):
            problems.append(f"make_chart.py draws a different chart from {CHART}. "
                            "If the change is intended: rerun make_chart.py and commit the new chart.")
    for p in problems:
        print("DIFFERS:", p)
    if not problems:
        print(f"Reproducible: {RESULTS} and {CHART} match a fresh run.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
