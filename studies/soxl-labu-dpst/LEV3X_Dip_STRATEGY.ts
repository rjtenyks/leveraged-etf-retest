# ============================================================================
# LEV3X_Dip  -  STRATEGY version (backtest in thinkorswim)
# ----------------------------------------------------------------------------
# Same four models as LEV3X_Dip_STUDY. Put it on a DAILY chart of SOXL, LABU
# or DPST with 5 years of data (time frame 5Y), then right-click any trade
# arrow > Show Report to see every trade. Entries and exits fill at the
# close. P/L is in dollars for tradeSize shares. To line up with the 5-year
# test, start the chart on Oct 7, 2021 (Custom time frame).
# Dates in the report: thinkorswim books a strategy order on the candle AFTER
# the signal, at the price given here (the signal day's close). So the report
# shows each trade one trading day later than the backtest, at the same
# prices. Checked Oct 7, 2026 on SOXL: 57 trades, prices match.
# Inputs: model, rsiLevel (10), maxHoldDays (10, RSI2_DIP only), tradeSize.
# ============================================================================
input model = {default RSI2_DIP, BOLLINGER_DIP, THREE_DOWN, TWO_SIGMA_DROP};
input rsiLevel = 10.0;
input maxHoldDays = 10;
input tradeSize = 100;

def m = if model == model.RSI2_DIP then 1 else if model == model.BOLLINGER_DIP then 2 else if model == model.THREE_DOWN then 3 else 4;
def c = close;
def chg = c - c[1];
def avgUp = WildersAverage(Max(chg, 0), 2);
def avgDn = WildersAverage(Max(-chg, 0), 2);
def rsi2 = if avgDn == 0 then 100 else 100 - 100 / (1 + avgUp / avgDn);
def sma5 = Average(c, 5);
def sma20 = Average(c, 20);
def lowerBand = sma20 - 2 * StDev(c, 20);
def ret = c / c[1] - 1;
def sigma60 = StDev(ret, 60)[1] * Sqrt(60 / 59);  # sample standard deviation, as in the backtest
def downStreak = CompoundValue(1, if c < c[1] then downStreak[1] + 1 else 0, 0);

def entrySig = if m == 1 then rsi2 < rsiLevel
    else if m == 2 then c < lowerBand
    else if m == 3 then downStreak >= 3
    else ret < -2 * sigma60;

def held = CompoundValue(1,
    if held[1] == 0 then (if entrySig then 1 else 0)
    else if (m == 1 and (c > sma5 or held[1] >= maxHoldDays))
         or (m == 2 and c > sma20)
         or (m == 3 and c > c[1])
         or (m == 4 and held[1] >= 3) then 0
    else held[1] + 1, 0);

AddOrder(OrderType.BUY_AUTO, held == 1, c, tradeSize, Color.GREEN, Color.GREEN, "dip buy");
AddOrder(OrderType.SELL_TO_CLOSE, held == 0 and held[1] > 0, c, tradeSize, Color.MAGENTA, Color.MAGENTA, "dip exit");
