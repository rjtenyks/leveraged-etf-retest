# leveraged-etf-retest

A 5-year retest of a SOXL · LABU · DPST pattern study, and the thinkorswim code for the rules that held up. The repo is meant to be public: write for an outside reader.

## Layout
- `backtests/soxl-labu-dpst/`: `fetch_prices.py` → `analyze.py` → `make_chart.py`. Python standard library only; run from the repo root.
- `studies/soxl-labu-dpst/`: thinkScript (`.ts`) files, each with a header comment saying what it does and its inputs.
- `notes/`: the full results. `docs/images/`: screenshots and the README chart.
- `data/`: downloaded prices and results, **git-ignored**.
- `tests/`: `unittest`, standard library only, no downloaded prices needed. Run from the repo root: `python3 -m unittest discover -s tests`. CI (`.github/workflows/tests.yml`) runs them on every pull request.

## Rules
- Numbers in README.md, notes and the thinkScript labels must come from `data/soxl-labu-dpst/results_5y.json`. When the analysis changes, rerun it, regenerate the chart, and update all three.
- A thinkScript rule change must still give the same trades as `analyze.py`. Check it before committing.
- Nothing personal in tracked files or images: no account numbers, balances, positions, names, emails, hostnames or locations. Check screenshots (pixels and metadata) before adding them.
- Tests must pass before a commit. A change to the statistics, the simulator or the chart gets a test.
- Record dated changes in CHANGELOG.md. Never backdate commits.
- Results are historical analysis, not advice. Keep the disclaimer.
