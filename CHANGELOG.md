# Changelog

Dates are when the work happened. This repo was created on 2026-10-07 from a private working repo, so its git history starts on that day; earlier work is recorded here instead of in backdated commits.

## 2026-10-09

- **Branch protection on `main`** ([#5](https://github.com/rjtenyks/leveraged-etf-retest/issues/5)): a change can only reach `main` through a pull request, after both `unittest` checks pass and with the branch up to date. It applies to admins too, and `main` can't be force-pushed or deleted. The code review of #4 pointed out that the README said "CI must pass" while nothing enforced it.

## 2026-10-08

- **Claude Code hook** ([#3](https://github.com/rjtenyks/leveraged-etf-retest/issues/3)): after Claude edits the analysis, the thinkScript files or the tests, a project hook runs the unit tests and returns any failures to Claude. After an edit to the analysis, it also runs a new reproducibility check (`check_reproducible.py`: rerun in a fresh folder, byte-compare the results and the chart) and flags changed numbers. The hook and the check have their own tests. The code review of the pull request found 14 issues. 13 were fixed: among them, a hang in the tests crashed the hook instead of stopping Claude, and a hook run took about 9 s (now about 4 s). The reason for leaving the last one is posted on the pull request.
- **Unit tests and CI** ([#1](https://github.com/rjtenyks/leveraged-etf-retest/issues/1)): standard-library tests for the statistics (against textbook values), the trade simulator, the chart script and the thinkScript headers, run by GitHub Actions on every pull request. 15 deliberate bugs, put in one at a time, were all caught. A code review found gaps in the first version (nine bugs that passed), and the tests were tightened until they failed too.
- Made this repo public. The interactive results page is shared view-only and now links here.

## 2026-10-07

- **Showcase repo:** this repo, with a case-study README and a chart script (`make_chart.py`). Rerunning the analysis here gives byte-identical results.
- **Cross-machine handoff:** a private claude.ai page with a shared database, a file store and downloads, for passing notes, code and files between the laptop, the PC and the phone. Planned in plan mode, with a confidential-information rule added before approval.
- **Checked in thinkorswim** on the Windows PC:
  - the daily study and the watchlist column match the backtest (SOXL RSI(2) 25.8, buy triggers 147.35 and 153.13)
  - the strategy report lists the same 57 trades at the same prices
- **Fixes from that testing:**
  - a next-session buy trigger in the study and the column
  - blue first-hour shading that the user can change
  - a note on thinkorswim's one-candle date shift in the strategy report
  - zip downloads for `.ts` files
  - the chart curves keep their final day
- **thinkorswim models:** `LEV3X_Dip` study, strategy and watchlist column, `LEV3X_Intraday` study, `LEV3X_TueNight` strategy. Their rule logic was checked against the backtest: identical trades for all 12 rule and fund pairs.
- **5-year retest:**
  - daily prices Oct 7, 2021 – Oct 6, 2026; hourly prices Nov 7, 2023 – Oct 6, 2026
  - 189 pattern tests with a false-discovery check, plus 8 trading rules on 3 funds
  - Python standard library only
  - results in `notes/soxl-labu-dpst-5yr-retest.md` and an interactive claude.ai results page

## 2026-09-25

- **Original two-year study** of SOXL, LABU and DPST (Sep 25, 2024 – Sep 24, 2026), as a claude.ai page. It's the starting point for this retest.
