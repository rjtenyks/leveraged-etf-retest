# Leveraged ETF retest: SOXL · LABU · DPST

[![tests](https://github.com/rjtenyks/leveraged-etf-retest/actions/workflows/tests.yml/badge.svg)](https://github.com/rjtenyks/leveraged-etf-retest/actions/workflows/tests.yml)

A September study found about 40 trading patterns in two years of prices for three 3x leveraged ETFs: semiconductors (SOXL), biotech (LABU) and regional banks (DPST). This project retests every one of them over five years, keeps the few that held up, and turns those into thinkorswim studies, a strategy and a watchlist column. They were loaded into thinkorswim and gave the backtest's numbers.

I built it with Claude Code. The code, the models and every number below came out of that collaboration, and each step was checked before the next one started.

![LABU in thinkorswim: the intraday study (left) and the daily dip model (right)](docs/images/labu-intraday-and-dip-study.png)

## What this repo shows

- **A question answered with data, including the answers that were no.** Most of the patterns failed the five-year test. The README says so up front.
- **Verification at every step.** Statistics were checked against textbook values. The trading rules were written twice, independently, and both versions gave identical trades. Then thinkorswim's own backtest gave the same 57 trades at the same prices.
- **Shipped into a real tool and fixed from real use.** The models run inside thinkorswim on a Windows PC. Testing them there led to four fixes. Those, and the other problems found along the way, are in [What broke and how we fixed it](#what-broke-and-how-we-fixed-it).
- **The results, as tools an AI can use.** A small MCP server answers questions from the saved results, and a mini eval checks Claude's answers against the published numbers. See [Ask the results (MCP server)](#ask-the-results-mcp-server).
- **An agent that checks the published numbers.** A read-only custom Claude Code agent checks every number in the README, the notes and the thinkScript labels against the results, with several auditors working at once. See [The numbers auditor](#the-numbers-auditor-a-custom-agent).
- **Hands-on agentic engineering.** This covers how the work was planned and checked, the guardrails used, and moving work between three machines. See [How it was built with Claude Code](#how-it-was-built-with-claude-code).

## The question

The original study covered Sep 2024 to Sep 2026. It flagged timing patterns ("Wednesdays are strong", "a flat open fades in the first hour", "buy when RSI(2) drops under 10") and rated each one as solid, worth watching, weak or no edge. Two years is short for funds that move 4–5% a day, so the question was: **which of these patterns survive five years that include the 2022 chip crash and the 2023 regional-bank crisis?**

## Results

![SOXL: growth of $1 over five years, buy and hold vs three dip-buying rules](docs/images/soxl-growth-5y.svg)

**Trading rules, Oct 7, 2021 to Oct 6, 2026**, after 0.05% cost per side, trading at the close. "Years up" counts the five 12-month periods that made money.

| Rule | SOXL | LABU | DPST |
|---|---|---|---|
| Buy & hold | +334%, worst drawdown −91% | −77%, −97% | −75%, −94% |
| **RSI(2) under 10**, sell on a close above the 5-day average or on day 10 | **+284%**, −62%, **up 5 of 5 years** | +74%, −56%, up 3 of 5 | +16%, −68% |
| **Close under the lower Bollinger band**, sell above the 20-day average (added in the retest) | **+558%**, −53%, **up 5 of 5** | −41% | −72% |
| **3 down days in a row**, sell on the first up day | **+226%**, −31%, up 4 of 5 | +9% | −76% |
| Tuesday close to Wednesday open | +119%, mostly in year 5 | **+88%, −23%, up 5 of 5** | +9% |

**Patterns:**
- Over 189 tests, 6 cleared p < 0.05, fewer than the roughly 9.5 that luck alone produces.
- Only one survives a Benjamini–Hochberg false-discovery check: SOXL tends to slip in the last 30 minutes after being up 6% or more at 3:30 pm.
- The structure of how these funds move held up for all three: most of a day's move comes overnight and in the first hour, bad days bottom late, and big opening gaps rarely fill the same day.

The full pattern-by-pattern comparison is in [notes/soxl-labu-dpst-5yr-retest.md](notes/soxl-labu-dpst-5yr-retest.md). An interactive version, with charts for each fund and the code, is the claude.ai page [SOXL · LABU · DPST Retest](https://claude.ai/artifact/6KbNAQx5n3ZkcqvesSobm9).

**Read with care:**
- Eight rules were tried on three funds, so the best results are probably flattered.
- SOXL's five years include a long semiconductor boom.
- Hourly prices only go back to Nov 2023, so the time-of-day results cover about three years, not five.

## How it was verified

1. **The statistics, checked against textbook values.** The project uses only the Python standard library, so the Welch t-test (through the regularized incomplete beta function) and the false-discovery adjustment were written by hand. They were checked against textbook values before use, for example t = 2.0 with 10 degrees of freedom gives p = 0.0734.
2. **Every test counted.** All 189 pattern tests are counted and corrected for multiple comparisons, not just the ones that looked good.
3. **Two implementations of every rule.**
   - The thinkScript logic was re-implemented separately in Python and compared trade by trade with the backtest.
   - The first comparison found one mismatch: thinkorswim's `StDev` divides by n, the backtest divides by n−1, and that changed three trades.
   - After the fix, all 12 rule and fund pairs gave identical trade dates.
4. **Checked inside thinkorswim.**
   - The daily study showed RSI(2) 25.8 and buy triggers of 147.35 and 153.13, matching the backtest to the cent.
   - The watchlist column matched on all three rows.
   - The strategy's own report listed the same 57 SOXL trades at the same prices.
5. **Reproducible.** Running `analyze.py` again in a fresh folder gives byte-identical results, and redrawing the chart gives the committed image. [`check_reproducible.py`](backtests/soxl-labu-dpst/check_reproducible.py) checks both.
6. **Unit tests.** The tests in [`tests/`](tests/) check the statistics against textbook values, the trade simulator against examples worked out by hand, the chart script, the thinkScript headers, the reproducibility check, the Claude Code hook, the MCP server and the eval's grading. To check the tests themselves, 15 different bugs were put into the code on purpose, one at a time, and the tests caught every one. GitHub Actions runs them on Python 3.12 and 3.14 for every pull request and every push to `main`, a pull request can't be merged until they pass, and a Claude Code hook runs them after Claude edits the code. They don't need the downloaded prices.

## The models in thinkorswim

| File | What it does |
|---|---|
| [`LEV3X_Dip_STUDY.ts`](studies/soxl-labu-dpst/LEV3X_Dip_STUDY.ts) | Daily chart: four dip rules, buy and sell arrows, today's and the next session's buy trigger, and a label with the rule's 5-year record on that fund |
| [`LEV3X_Dip_STRATEGY.ts`](studies/soxl-labu-dpst/LEV3X_Dip_STRATEGY.ts) | The same rules as a strategy, for thinkorswim's own backtest report |
| [`LEV3X_Dip_COLUMN.ts`](studies/soxl-labu-dpst/LEV3X_Dip_COLUMN.ts) | Watchlist column: BUY / SELL / HOLD, or RSI(2) with both buy triggers |
| [`LEV3X_Intraday_STUDY.ts`](studies/soxl-labu-dpst/LEV3X_Intraday_STUDY.ts) | 5-minute chart: gap-fill odds, the typical dip below the open, first-hour shading, and the time-of-day patterns that held |
| [`LEV3X_TueNight_STRATEGY.ts`](studies/soxl-labu-dpst/LEV3X_TueNight_STRATEGY.ts) | Buy Tuesday's close, sell Wednesday's open |

Each study reads the chart's symbol and shows that fund's own numbers. Setup steps are in [studies/soxl-labu-dpst/README.txt](studies/soxl-labu-dpst/README.txt).

![LEV3X watchlist column](docs/images/lev3x-watchlist-column.png)

The strategy replayed on SOXL, five years of daily candles:

![LEV3X_Dip_STRATEGY trades on SOXL](docs/images/soxl-dip-strategy-trades.png)

## What broke and how we fixed it

| Problem | Root cause | Fix | Result |
|---|---|---|---|
| Time-of-day tests couldn't cover five years | Yahoo keeps about 730 sessions of hourly bars; older intraday data from Alpha Vantage is a paid endpoint | Ran those tests on the three years available, and said so everywhere | Honest scope instead of a silent gap |
| No pandas, and pip couldn't be installed on the laptop | Ubuntu's Python lacked `ensurepip` for virtual environments | Wrote the statistics on the standard library and tested them against known values | Runs anywhere with Python 3, nothing to install |
| Three extra trades on one rule in the thinkScript version | Population vs sample standard deviation | Scaled thinkorswim's `StDev` by √(60/59) | Identical trades in both versions |
| A chart's end labels read low ($4.06 instead of $4.34) | Curves were saved every 5th day, which dropped the final day | Always keep the last point | Caught by a screenshot review before release |
| Buy trigger of 158.80 instead of 147.35 | The study was on an intraday chart, so RSI(2) used minute bars | Diagnosed from how close the trigger sat to the price; documented the chart settings (1Y 1D, 5D 5m) | Values matched once on daily candles |
| "Today's trigger" was out of date after the close | The label only looked at the current session | Added the next session's trigger to the study and the column | The after-hours number is the useful one |
| First-hour shading blended into thinkorswim's own gray | Color choice | A blue the user can change in the study settings | Visible on the default dark theme |
| Strategy report dates one day later than the backtest | thinkorswim books strategy orders on the next candle | Confirmed the prices matched, then documented the shift | Trades verified as identical |
| `.ts` files couldn't be downloaded from the results page | The page viewer only allows certain file types | Built a small zip writer (stored entries, CRC-32) into the page | One-click download, checked with `unzip -t` |

## How it was built with Claude Code

- **Three machines.** Claude Code runs on an Ubuntu laptop. thinkorswim runs on a Windows PC, and a phone is used for checks on the go. Manual steps on the other machines were given one at a time, each checked before the next.
- **Instructions and memory.** A global `CLAUDE.md` holds my working preferences and security rules, and each repo has its own `CLAUDE.md`. Claude Code keeps short memory notes between sessions (how I like steps delivered, which channel to use for which machine).
- **Guardrails.**
  - Global git `pre-commit` and `pre-push` hooks run gitleaks and a list of private values on every commit in every repo. They are never bypassed.
  - Screenshots were checked for account numbers and file metadata before they went into the repo.
  - A standing rule: no passwords, card numbers, keys or account numbers in anything shared, without my explicit approval.
- **A project hook that runs the tests.**
  - [`.claude/settings.json`](.claude/settings.json) registers a `PostToolUse` hook. After Claude edits the analysis, the thinkScript files, the tests, the MCP server, the eval or the hook itself, [`run_tests.py`](.claude/hooks/run_tests.py) runs the unit tests. If they fail or hang, the hook hands that back to Claude, which fixes it before moving on.
  - After an edit to the analysis, it also reruns the reproducibility check on the downloaded prices. A crash there stops Claude the same way. When the numbers change, it tells Claude, because the README, the notes and the thinkScript labels then need updating too.
  - It's committed with the repo, so it works for anyone who opens the project in Claude Code. The hook has its own tests.
- **Issues, pull requests and review.** Starting with the unit tests ([#1](https://github.com/rjtenyks/leveraged-etf-retest/issues/1)), each change is a GitHub issue and a pull request. Branch protection on `main` enforces part of this: a change can only arrive through a pull request that is up to date with `main`, and only after the unit tests pass on every Python version CI runs. While protection is on, it holds for me as the admin too. Its settings are in [`.github/branch-protection.json`](.github/branch-protection.json). GitHub can't tell whether a pull request weakened the tests or the workflow that runs them, so the review covers that: Claude Code's `/code-review` reviews each pull request before I merge it, and its findings, and what was done about each, are posted on the pull request.
- **Plan mode.** The cross-machine handoff page was planned first. I corrected the plan to add the confidential-information rule and its checks, then approved it.
- **Connectors (MCP).**
  - Google Drive moved files from the PC to the laptop early on.
  - Alpha Vantage was checked as a source of intraday history, which is where the paid-data limit showed up.
  - This repo has its own MCP server, for the results (next section).
- **claude.ai pages with runtime capabilities.**
  - The interactive results page has per-fund charts and Copy and Download buttons for the code.
  - A private "handoff" page has a small shared database, a file store and downloads, so notes, code and screenshots move between the laptop, the PC and the phone. The screenshots in this README arrived that way.

## Ask the results (MCP server)

[`mcp_server/`](mcp_server/) is a small, read-only [MCP](https://modelcontextprotocol.io) server. With it, Claude, or any MCP client, answers questions about this retest from the saved results instead of from memory.

| Tool | What it answers |
|---|---|
| `get_results(fund)` | Every trading rule on SOXL, LABU or DPST, best first: total return, each year's return, worst drawdown, trades, win rate |
| `compare_funds(rule)` | One rule on all three funds, side by side. Rule names are matched loosely: "RSI(2)", "bollinger", "3 down days" |
| `pattern_verdict(query, fund)` | Any of the 189 pattern tests, with its p-value, its q-value after the false-discovery check, and a verdict: held up, probably luck, or no evidence |
| `get_section(fund, section)` | The other numbers: price structure (biggest moves, how often opening gaps fill), signals, weekdays, FOMC and calendar days, VIX levels, time of day. Each section comes with what its fields mean |

- **Design.** The answers are plain Python in [`results.py`](mcp_server/results.py), tested without the MCP package. [`server.py`](mcp_server/server.py) is a thin layer on top, built with the official Python SDK (`mcp` 2.3.0). A question it can't answer, such as an untested fund or a missing results file, comes back as a tool error that says what to do.
- **Tests.** The answers are tested on a hand-made results file with values right at the cutoffs. The server is tested end to end over the MCP protocol, including starting it from the command in [`.mcp.json`](.mcp.json), as Claude Code does. CI installs the packages from [`requirements.txt`](requirements.txt), each pinned with its hash.
- **Mini eval.** [`evals/run_evals.py`](evals/run_evals.py) asks Claude nine questions with known answers through `claude -p`. It runs from an empty folder, with Claude Code's own tools turned off and only this server available. Each answer must contain the published numbers and no invented ones, and Claude must have called a fitting tool. Nothing runs, and nothing is paid for, unless the `claude` CLI, `.venv` and current results are all in place. The first run scored 7 of 8. The miss was the grader's: Claude wrote "lost 76.8%", and the check only accepted "−76.8%". With that fixed: 8 of 8, in 35 seconds. A ninth question, for `get_section`, came later; all nine pass.

To use it in Claude Code, set up the environment once (below), start `claude` in this folder, and approve the project's MCP server when asked. On Windows, change the command in [`.mcp.json`](.mcp.json) to `.venv\Scripts\python.exe`. Then ask, for example, "Did the FOMC-day pattern hold up on SOXL?"

## The numbers auditor (a custom agent)

[`.claude/agents/numbers-auditor.md`](.claude/agents/numbers-auditor.md) is a custom Claude Code agent, committed with the repo like the hook. Given a document, it finds every number that states a result, looks each one up through the MCP server, and reports the ones that don't match, with the right value and where it came from.

- **Read-only.** Its only tools read files and query the MCP server, so several auditors can work on the same files at once. Agents that edit files at the same time would each need their own copy of the repo (a git worktree); these don't.
- **Scaling out.** The README, the notes and the thinkScript files go to three auditors running at the same time: about 330 numbers checked in about 40 seconds, about half the time of one after another.
- **What its first runs found.** Two numbers in the intraday study's labels, LABU's and DPST's worst-10% day, couldn't be traced to the saved results. The agent listed them as "not found" instead of guessing. They were right, but `analyze.py` computed them without saving them, which broke this repo's own rule; now it saves them. Reporting a planted error, the agent also gave the hourly day count per fund: 720 for SOXL, but 721 for LABU and DPST, where the notes said 720 for all three.
- **Eval.** [`evals/eval_auditor.py`](evals/eval_auditor.py) plants seven wrong numbers (swapped digits, a flipped sign, nearby values) in a temporary copy of the documents and runs the three auditors on it. On Sonnet, they caught all 7, flagged nothing else, and gave the right value and its source for each, for about 50 cents. Haiku, at a tenth of the cost, caught 5, raised a false alarm and once returned no report, so the agent uses Sonnet. (Haiku's false alarm pointed at an ambiguous phrase in the notes, "negative in 2021–2023", which now names the years it means.) With `--clean`, the same script audits the real documents.

To use it in Claude Code, ask for it by name, for example "Use the numbers-auditor agent to check the README and the notes". For several files, Claude runs several auditors in parallel.

## Run it

The analysis needs only Python 3's standard library. The MCP server needs the packages in `requirements.txt`. Prices are downloaded into `data/`, which is not in the repo.

```
python3 backtests/soxl-labu-dpst/fetch_prices.py   # daily and hourly prices from Yahoo Finance
python3 backtests/soxl-labu-dpst/analyze.py        # all tests and backtests -> data/soxl-labu-dpst/results_5y.json
python3 backtests/soxl-labu-dpst/make_chart.py     # the chart above -> docs/images/soxl-growth-5y.svg
python3 -m unittest discover -s tests             # the unit tests (no prices needed)
python3 backtests/soxl-labu-dpst/check_reproducible.py   # rerun in a fresh folder, compare results and chart
```

For the MCP server and its tests:

```
python3 -m venv .venv
.venv/bin/pip install --require-hashes --only-binary :all: -r requirements.txt   # exactly the pinned, hashed packages
.venv/bin/python -m unittest discover -s tests    # all the tests, the MCP server's included
python3 evals/run_evals.py                         # the mini eval: needs Claude Code, signed in; a few cents of usage
python3 evals/eval_auditor.py                      # the numbers auditor's eval (--clean audits the real documents); about 50 cents
```

`requirements.txt` is generated from `requirements.in` with `pip-compile --generate-hashes` ([pip-tools](https://github.com/jazzband/pip-tools)), so it isn't edited by hand.

On Windows, Python has no built-in time-zone database, so run `pip install tzdata` first ([Python docs](https://docs.python.org/3/library/zoneinfo.html#data-sources)). Linux and macOS need nothing extra.

Yahoo only serves recent hourly bars, so a fresh download covers a later window and gives slightly different numbers from the ones above.

## Layout

| Folder | What's in it |
|---|---|
| `backtests/soxl-labu-dpst/` | Price download, analysis and chart scripts |
| `studies/soxl-labu-dpst/` | The thinkScript files and their setup notes |
| `notes/` | The full results, pattern by pattern |
| `docs/images/` | Screenshots and the chart |
| `mcp_server/` | The MCP server: the answers ([`results.py`](mcp_server/results.py)) and the server ([`server.py`](mcp_server/server.py)) |
| `evals/` | The evals for the MCP server and the numbers auditor |
| `tests/` | Unit tests, standard library `unittest` |
| `.github/` | CI that runs the tests on every pull request ([`workflows/tests.yml`](.github/workflows/tests.yml)), and the branch protection settings that block a merge until they pass ([`branch-protection.json`](.github/branch-protection.json)) |
| `.claude/` | Claude Code project settings, the hook that runs the tests after each edit, and the numbers-auditor agent |
| `.mcp.json` | Tells Claude Code how to start the MCP server |
| `requirements.in`, `requirements.txt` | The MCP server's one dependency, and every package it needs, pinned with hashes |
| [`CHANGELOG.md`](CHANGELOG.md) | What was done and when |

## Disclaimer

Historical analysis for research and education, not investment advice. 3x leveraged ETFs can lose most of their value quickly. thinkorswim is a Charles Schwab platform; this project isn't affiliated with Schwab or Direxion.

The code is shared for review. All rights reserved.
