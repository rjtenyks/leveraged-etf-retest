# leveraged-etf-retest

A 5-year retest of a SOXL · LABU · DPST pattern study, and the thinkorswim code for the rules that held up. The repo is meant to be public: write for an outside reader.

## Layout
- `backtests/soxl-labu-dpst/`: `fetch_prices.py` → `analyze.py` → `make_chart.py`. Python standard library only; run from the repo root.
- `studies/soxl-labu-dpst/`: thinkScript (`.ts`) files, each with a header comment saying what it does and its inputs.
- `notes/`: the full results. `docs/images/`: screenshots and the README chart.
- `data/`: downloaded prices and results, **git-ignored**.
- `mcp_server/`: the MCP server. `results.py` holds the answers (standard library only); `server.py` wraps them as tools with the `mcp` SDK. `.mcp.json` starts it. `evals/run_evals.py` is its mini eval: it runs real `claude -p` requests and costs usage, so run it when the tools, their descriptions or the results change, not after every edit.
- `tests/`: `unittest`, standard library only, no downloaded prices needed. Run from the repo root: `.venv/bin/python -m unittest discover -s tests` (with plain `python3`, the MCP server tests skip). CI (`.github/workflows/tests.yml`) runs them on every pull request, and its `tests-passed` job must pass before a merge.
- `.claude/`: a project hook. After an Edit or Write under `backtests/`, `studies/`, `tests/`, `mcp_server/`, `evals/` or `.claude/`, `hooks/run_tests.py` runs the tests, with `.venv`'s Python when it exists. After one under `backtests/` it also runs `check_reproducible.py`, which skips when the downloaded prices or saved results aren't there. Edits made through Bash don't trigger it, so run the tests yourself after those.

## Rules
- Numbers in README.md, notes and the thinkScript labels must come from `data/soxl-labu-dpst/results_5y.json`. When the analysis changes, rerun it, regenerate the chart, and update all three.
- A thinkScript rule change must still give the same trades as `analyze.py`. Check it before committing.
- Nothing personal in tracked files or images: no account numbers, balances, positions, names, emails, hostnames or locations. Check screenshots (pixels and metadata) before adding them.
- `main` is protected (settings: `.github/branch-protection.json`). Work on a branch and never commit to `main`: changes arrive only through pull requests that are up to date with `main` and pass `tests-passed`. If a pull request falls behind `main`, update it with `gh api -X PUT repos/rjtenyks/leveraged-etf-retest/pulls/<n>/update-branch`, then wait for CI again.
- Never change or remove the branch protection, or rename the `tests-passed` job, without the user's explicit approval.
- The analysis stays standard-library only. The MCP server's packages live in `.venv` (git-ignored). `requirements.txt` is generated from `requirements.in` with `pip-compile --generate-hashes`; never edit it by hand.
- After editing a workflow, check that it parses before pushing: `python3 -c "import sys, yaml; yaml.safe_load(open(sys.argv[1]))" .github/workflows/tests.yml`. GitHub runs nothing from a workflow it can't read.
- Tests must pass before a commit. A change to the statistics, the simulator or the chart gets a test.
- Record dated changes in CHANGELOG.md. Never backdate commits.
- Results are historical analysis, not advice. Keep the disclaimer.
