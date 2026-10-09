# SOXL · LABU · DPST: 5-year retest

The claude.ai page "SOXL · LABU · DPST Patterns" tested two years (Sep 25, 2024 – Sep 24, 2026). This retest runs the same tests over five years and builds thinkorswim code for the models that held up.

The same results with charts per fund, and the code with copy buttons: [SOXL · LABU · DPST Retest](https://claude.ai/artifact/6KbNAQx5n3ZkcqvesSobm9).

- **Daily tests:** Oct 7, 2021 – Oct 6, 2026, 1,254 sessions per fund. These five years include the 2022 chip crash (SOXL −71% in year 1) and the March 2023 regional-bank crisis (DPST −36% in one day).
- **Time-of-day tests:** Yahoo keeps hourly bars back to Nov 7, 2023 only: 720 full days for SOXL and 721 for LABU and DPST, about 3 years. Alpha Vantage sells older intraday data on a paid plan only. "3 of 3 years" below means the same direction in each of the three 12-month periods.
- **Method:** same definitions as the page (Wilder RSI, Bollinger 20 ± 2, 2-sigma = twice the trailing 60-day standard deviation). Trades at the close, 0.05% cost per side, dividends included. Code in `backtests/soxl-labu-dpst/`. The prices are in `data/soxl-labu-dpst/` (not in git).
- **Not retested:** CPI days. No source of past CPI release dates was reachable from this laptop (BLS blocks downloads). The page rated it weak (p = 0.6).

Historical analysis only, not advice.

## The short version

- **Most of the page's "watch" patterns faded.** Over 189 tests, 6 came in under p < 0.05, fewer than the ~9.5 that luck alone produces. One survives the false-discovery check: SOXL fading in the last 30 minutes after being up 6%+ at 3:30.
- **The volatility structure held for all three funds:** big overnight gaps, a busy first hour, late lows on bad days, and big gaps rarely filling.
- **Dip-buying worked on SOXL in every one of the five years**, including the 2022 crash year. It half-worked on LABU and failed on DPST.
- **DPST trended.** After 3+ down days it kept falling (next day −0.61% on average, in all 5 years). Every dip rule on it lost money or went nowhere.

## Trading rules, 5 years

After 0.05% cost per side. "Years up" counts the 12-month periods (Oct 7 to Oct 6) with a gain.

| Rule | SOXL | LABU | DPST |
|---|---|---|---|
| Buy & hold | +334%, drawdown −91% | −77%, drawdown −97% | −75%, drawdown −94% |
| **RSI(2) < 10, sell above 5-day avg or day 10** | **+284%**, 57 trades, 65% won, −62%, **5 of 5 years** | +74%, 63 trades, −56%, 3 of 5 | +16%, 71 trades, −68%, 4 of 5 |
| **Close below lower Bollinger, sell above 20-day avg** (new) | **+558%**, 24 trades, 79% won, −53%, **5 of 5** | −41%, −76%, 2 of 5 | −72%, −82%, 2 of 5 |
| **3 down days, sell first up day** | **+226%**, 67 trades, 73% won, −31%, 4 of 5 | +9%, −37%, 4 of 5 | −76%, −83%, 0 of 5 |
| 2-sigma drop, hold 3 days | −49%, −71%, 2 of 5 | +115%, −51%, 3 of 5 | −9%, −61%, 2 of 5 |
| Tuesday close → Wednesday open | +119%, −55% (almost all in year 5) | **+88%, −23%, 5 of 5** | +9%, −49%, 3 of 5 |
| Overnight only, before costs | +518% | +170% | +64% |
| Market hours only, before costs | −30% | −91% | −85% |

Read with care:
- Eight rules were tried on three funds. Picking the best of 24 after the fact makes it look better than it will be.
- The Bollinger rule wasn't on the page; it was added here.
- SOXL's five years include a semiconductor boom. Its dips have bounced, and that could change.
- Holding only overnight beat holding during market hours for all three funds, but a round trip every day costs more than the gap earns on LABU and DPST.

## Pattern by pattern

| Pattern | 2-year page | Retest | Verdict |
|---|---|---|---|
| **SOXL** | | | |
| Moves are front-loaded | overnight 3.9%, first hour 2.6%, midday ~1.1% | 3.6%, 2.5%, ~1.0–1.2% | Holds |
| Down days do their damage early | 70% overnight + first hour | 67% | Holds |
| Bad days bottom late | worst-10% days: low after 2:30 on 60% | 59% | Holds |
| Big gaps rarely fill | 5%+ down 28%, 5%+ up 18% | 27% (n=115), 21% (n=150), 5 yrs | Holds |
| Volatility clusters | 2σ after 2σ 9% vs 6% | 10.7% vs 6.0% | Holds |
| Typical drop from the open | median −3.0%, 1 in 10 −9.4% | −3.0%, −9.0% | Holds |
| Late fade when up 6%+ at 3:30 | −0.34%, fell 59%, p=0.005 | −0.27%, fell 58%, p=0.0002, 2 of 3 years | **Holds, the strongest result** |
| Big gap-downs: first-hour bounce, then fade | +1.33%, then −0.87% | bounce +0.94% (mostly the last year); 10:30→close −1.34%, 3 of 3 years, p=0.03 | Fade holds, bounce doesn't |
| Wednesdays | median +2.15%, p=0.036 | mean +0.86%, p=0.24; mostly the last 2 years | Faded |
| Gains came overnight | +424% vs −20% | +518% vs −30% (before costs) | Holds |
| Oversold bounces | RSI(2)<10 next day +2.69%, p=0.24 | +1.40%, p=0.17, 4 of 5 years; below lower band +2.52%, 5 of 5 | Still weak day by day; the rules built on it worked |
| Losing streaks | no edge | after 3+ down days next day +1.22% vs +0.38%, 5 of 5 years, p=0.18 | Now a weak lean up |
| FOMC decision day | not flagged | +2.48%, 65% up, 4 of 5 years, p=0.08 | New weak lean |
| Week low on Mon/Fri, calendar effects | no edge | no edge | Same |
| CPI days | weak | not retested | — |
| **LABU** | | | |
| Gap-ups keep running in the first hour | +0.87%, p=0.008 | +0.75%, up 60%, 3 of 3 years, p=0.001 | **Holds** |
| Flat opens fade early | −0.44%, p=0.045 | −0.50%, up 45%, 3 of 3 years, p=0.002 | **Holds, stronger** |
| Wednesdays / Tuesday-night gap | median +1.82%, gap p=0.009 | gap +0.38%, p=0.07, positive all 5 years | Weaker but consistent |
| Day after the Fed | +2.8%, p=0.010 | +0.34%, p=0.77 (negative in the first two years, Oct 2021 – Oct 2023) | Fails |
| Big up days give some back | −0.95% next day | +0.03% | Fails |
| Deep pullbacks recovered | next 5 days +4.3% | 30%+ below 20-day high: +1.77% vs +0.23% | Still weak |
| Standard oversold levels | no edge | RSI(14)<30 next day +2.5%, p=0.05, 4 of 4 years | Weak lean |
| Structure (gaps, late lows, front-loading) | | gap fills 31% / 20% for 5%+ gaps; late low 60%; drop from open −3.3% median | Holds |
| **DPST** | | | |
| Quiet afternoons drift lower | −0.24%, p=0.002 | −0.15%, p=0.11; flat (+0.04%) in hourly year 3, Nov 7, 2023 – Oct 6, 2024 | Weakened |
| Overbought readings faded | RSI(14)>70 next 5 days −3.85%, p=0.013 | −1.30%, p=0.68 | Fails |
| Gap-downs extend, then recover | first hour −0.68%, rest +1.33% | −0.17%, then +0.75% (p=0.08) | Weakened |
| Gap-ups fade after 10:30 | not flagged | −0.57%, up 45%, 3 of 3 years, p=0.03 | New |
| Fed days hurt, day after helped | −2.5% / +1.8% | −0.25% / −0.49%, mixed years | Fails |
| Oversold didn't bounce | RSI(2)<10 next 5 days −1.18% | −0.62%; after 3+ down days, next day −0.61% in all 5 years | Holds: don't buy DPST dips |
| Structure | | gap fills 25% / 24% for 5%+ gaps; late low 52%; 2σ after 2σ 14% vs 6% | Holds |

## What's in thinkorswim

`studies/soxl-labu-dpst/` holds the code. Each chart label carries the numbers above.

- **LEV3X_Dip** (study, strategy, watchlist column): the four dip models with their 5-year record per fund. SOXL: RSI(2), Bollinger or 3-down. LABU: RSI(2). The DPST row shows "no edge". The thinkScript rules were checked against the backtest and gave identical trade dates for all 12 model and fund pairs.
- **LEV3X_Intraday** (study): gap-fill odds, typical dip below the open, first-hour shading, and only the time-of-day patterns that held: SOXL's 3:30 fade and gap-down fade, LABU's first hour after a gap-up or a flat open, DPST's gap-up fade.
- **LEV3X_TueNight** (strategy): the Tuesday-night gap, for checking in thinkorswim's report.

## Readings at the Oct 6, 2026 close

- **SOXL** 164.26: RSI(2) 95.8, no dip.
- **LABU** 230.95: RSI(2) 14.3, and it closed below its lower Bollinger band. The Bollinger rule lost money on LABU, so that signal isn't a model here.
- **DPST** 112.02: RSI(2) 29.4.
- **VIX** 15.0.

## Re-run

From the repo root:

```
python3 backtests/soxl-labu-dpst/fetch_prices.py
python3 backtests/soxl-labu-dpst/analyze.py
```

Both use only the Python standard library. Results are written to `data/soxl-labu-dpst/results_5y.json`.
