SOXL - LABU - DPST MODELS - thinkorswim files
Built Oct 7, 2026 from a 5-year retest of the "SOXL · LABU · DPST Patterns" study (which tested 2 years).
Results and method: notes/soxl-labu-dpst-5yr-retest.md. Backtest code: backtests/soxl-labu-dpst/.
Historical analysis only; not a recommendation or investment advice. Paper-trade first.

FILES
  LEV3X_Dip_STUDY.ts          Daily chart. Four dip-buying models (pick one with the "model" input),
                              buy/sell arrows, today's buy trigger, exit line, and a label with the
                              model's 5-year result on this fund.
  LEV3X_Dip_STRATEGY.ts       The same four models as a strategy, for thinkorswim's "Show report".
  LEV3X_Dip_COLUMN.ts         Watchlist column: BUY / SELL / HOLD for the RSI(2) model on each row.
  LEV3X_Intraday_STUDY.ts     Intraday chart (5-30 minute). Yesterday's close, gap-fill odds, typical dip
                              below the open, first-hour shading, and the time-of-day patterns that held.
  LEV3X_TueNight_STRATEGY.ts  Strategy: buy at Tuesday's close, sell at Wednesday's open.

WHAT HELD UP OVER 5 YEARS (Oct 7, 2021 - Oct 6, 2026, 0.05% cost per side)
  SOXL  RSI(2) dip      +284%, 57 trades, 65% won, drawdown -62%, up every year (buy & hold +334%, -91%)
        Bollinger dip   +558%, 24 trades, 79% won, drawdown -53%, up every year (new rule, added in the retest)
        3 down days     +226%, 67 trades, 73% won, drawdown -31%, up 4 of 5 years
  LABU  RSI(2) dip      +74%, 63 trades, drawdown -56%, up 3 of 5 years (buy & hold -77%)
        Tuesday night   +88%, drawdown -23%, up every year (could still be luck: p = 0.07)
  DPST  nothing. Every dip rule lost money or barely broke even with drawdowns of 61-83%.
  Time of day (hourly prices, Nov 2023 - Oct 2026):
        SOXL up 6%+ at 3:30 -> last 30 minutes averaged -0.27% (the one result that passes the
             multiple-testing check)
        LABU gap up 2%+ -> first hour +0.75%; flat open -> first hour -0.50% (both in all 3 years)
        SOXL gap down 5%+ and DPST gap up 2%+ -> 10:30 to the close fades (all 3 years)

1. IMPORT (thinkorswim desktop)
  Charts > Studies (flask icon) > Edit studies... > Import > pick LEV3X_Dip_STUDY.ts, then
  LEV3X_Intraday_STUDY.ts. Strategies tab > Import > the two _STRATEGY.ts files.
  If Import fails: Create..., delete the placeholder line, paste the file's text, name it like the file.
  To update a study: Import the new file. thinkorswim asks to overwrite the old one; confirm.

2. CHARTS (two charts side by side: grid icon > 1 x 2)
  Left, time frame 1Y, aggregation 1D (daily candles): SOXL with LEV3X_Dip (model RSI2_DIP or
  BOLLINGER_DIP), or LABU (RSI2_DIP). On any other aggregation the RSI(2) is not the tested signal.
  Right, 5D 5m: the same symbol with LEV3X_Intraday. The first hour is shaded blue; change the color
  in the study settings under Globals.
  The studies read the symbol (input fund = AUTO). On another symbol they say "no test".

3. WATCHLIST COLUMN
  Right-click a column header > Customize... > Custom column > paste LEV3X_Dip_COLUMN.ts, aggregation D.
  Put SOXL, LABU and DPST in the watchlist. Green = buy at the close, magenta = sell at the close,
  cyan = in a trade, yellow = RSI(2) under 20, gray DPST row = no edge.
  When flat it reads e.g. "RSI 12 buy<223.66 nxt<225.7": today's trigger, then the next session's.

4. CHECK THE BACKTEST INSIDE THINKORSWIM
  Daily chart, Custom time frame from Oct 7, 2021, add LEV3X_Dip_STRATEGY with the same model,
  right-click a "dip buy" / "dip exit" marker (not the study's plain arrows) > Show report.
  The report books each order on the candle AFTER the signal, at the signal day's close: the prices match
  the backtest, the dates read one trading day later. Checked Oct 7, 2026 on SOXL: 57 trades (114 rows),
  prices match. Dollar results differ a little because thinkorswim doesn't add dividends back.

5. HOW TO RUN IT (all models trade at the close)
  3:55 pm ET: look at the column or the chart label. BUY at the close = buy before 4:00 pm.
  SELL at the close = sell before 4:00 pm. A market-on-close order does both without watching the clock.
  These are 3x funds: a -62% drawdown on the best model is normal for them. Size so that you can live
  with that.
