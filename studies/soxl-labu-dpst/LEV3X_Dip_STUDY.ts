# ============================================================================
# LEV3X_Dip  -  dip-buying models for SOXL, LABU and DPST (daily chart)
# ----------------------------------------------------------------------------
# Put this on a DAILY chart of SOXL, LABU or DPST. Every model buys and sells
# at the 4:00 pm close, so decide in the last minutes (3:55 pm ET).
# Pick a model with the "model" input:
#   RSI2_DIP        BUY when RSI(2) is below 10. SELL on a close above the
#                   5-day average (cyan line) or at the close of day 10.
#   BOLLINGER_DIP   BUY on a close below the lower Bollinger band (20, 2).
#                   SELL on a close above the 20-day average (cyan line).
#   THREE_DOWN      BUY at the 3rd lower close in a row. SELL at the first
#                   close above the day before (cyan line).
#   TWO_SIGMA_DROP  BUY after a one-day drop bigger than 2 x the 60-day
#                   volatility. SELL at the close 3 days later.
# Orange dashes = today's buy trigger (a close below it = BUY), where the
# model has one. The orange labels give today's trigger and the next
# session's, worked out from the latest price. The second label shows how
# the model did on this fund in the 5-year test (Oct 7, 2021 - Oct 6, 2026,
# 0.05% cost per side).
# Historical analysis only, not advice.
# Inputs: model, rsiLevel (10), maxHoldDays (10, RSI2_DIP only), fund (AUTO
# reads the chart symbol; set it by hand if the label says "no 5-year test").
# ============================================================================
declare upper;

input model = {default RSI2_DIP, BOLLINGER_DIP, THREE_DOWN, TWO_SIGMA_DROP};
input rsiLevel = 10.0;
input maxHoldDays = 10;
input fund = {default AUTO, SOXL, LABU, DPST};

def sym = if fund == fund.SOXL then 1 else if fund == fund.LABU then 2 else if fund == fund.DPST then 3
    else if GetSymbol() == "SOXL" then 1 else if GetSymbol() == "LABU" then 2 else if GetSymbol() == "DPST" then 3 else 0;
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

# held = day number in the trade (1 = entry day), 0 = flat
def held = CompoundValue(1,
    if held[1] == 0 then (if entrySig then 1 else 0)
    else if (m == 1 and (c > sma5 or held[1] >= maxHoldDays))
         or (m == 2 and c > sma20)
         or (m == 3 and c > c[1])
         or (m == 4 and held[1] >= 3) then 0
    else held[1] + 1, 0);

# today's buy trigger, from yesterday's close
def k = (100 - rsiLevel) / rsiLevel;
def rsiTrig = if k * avgUp >= avgDn then c - (k * avgUp - avgDn) else c + (avgDn / k - avgUp);
def trigToday = if m == 1 then rsiTrig[1]
    else if m == 3 and downStreak[1] >= 2 then c[1]
    else if m == 4 then c[1] * (1 - 2 * sigma60)
    else Double.NaN;
# next session's buy trigger, from this bar's close (or the live price during the session)
def trigNext = if m == 1 then rsiTrig
    else if m == 3 and downStreak >= 2 then c
    else if m == 4 then c * (1 - 2 * StDev(ret, 60) * Sqrt(60 / 59))
    else Double.NaN;
# today's exit level: a close above it ends the trade
def exitToday = if m == 1 then Average(c, 4)[1] else if m == 2 then Average(c, 19)[1] else if m == 3 then c[1] else Double.NaN;

plot EntryTrigger = if held[1] == 0 then trigToday else Double.NaN;
EntryTrigger.SetDefaultColor(Color.ORANGE);
EntryTrigger.SetStyle(Curve.SHORT_DASH);

plot ExitLevel = if held[1] > 0 then exitToday else Double.NaN;
ExitLevel.SetDefaultColor(Color.CYAN);
ExitLevel.SetLineWeight(2);

plot LowerBB = if m == 2 then lowerBand else Double.NaN;
LowerBB.SetDefaultColor(Color.GRAY);

plot BuyArrow = if held == 1 then low else Double.NaN;
BuyArrow.SetPaintingStrategy(PaintingStrategy.ARROW_UP);
BuyArrow.SetDefaultColor(Color.GREEN);
BuyArrow.SetLineWeight(3);

plot SellArrow = if held == 0 and held[1] > 0 then high else Double.NaN;
SellArrow.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);
SellArrow.SetDefaultColor(Color.MAGENTA);
SellArrow.SetLineWeight(3);

AssignPriceColor(if held > 0 then Color.CYAN else Color.CURRENT);

AddLabel(yes,
    (if m == 1 then "RSI(2) dip" else if m == 2 then "Bollinger dip" else if m == 3 then "3 down days" else "2-sigma drop")
    + "  |  RSI(2) " + Round(rsi2, 1) + "  |  " + Round((c / lowerBand - 1) * 100, 1) + "% from lower band",
    if entrySig then Color.GREEN else Color.GRAY);

# 5-year results of each model on each fund (backtests/soxl-labu-dpst/analyze.py)
AddLabel(yes,
    if sym == 0 then "No 5-year test for " + GetSymbol() + " (set the fund input)"
    else if sym == 1 and m == 1 then "SOXL 5 yrs: +284% (31%/yr), 57 trades, 65% won, worst drawdown -62%, up 5 of 5 years. Buy & hold +334%, drawdown -91%"
    else if sym == 1 and m == 2 then "SOXL 5 yrs: +558% (46%/yr), 24 trades, 79% won, worst drawdown -53%, up 5 of 5 years (rule added in the retest)"
    else if sym == 1 and m == 3 then "SOXL 5 yrs: +226% (27%/yr), 67 trades, 73% won, worst drawdown -31%, up 4 of 5 years"
    else if sym == 1 then "SOXL 5 yrs: -49%, 33 trades, 39% won, worst drawdown -71%, up 2 of 5 years. Not a model"
    else if sym == 2 and m == 1 then "LABU 5 yrs: +74% (12%/yr), 63 trades, 64% won, worst drawdown -56%, up 3 of 5 years. Buy & hold -77%"
    else if sym == 2 and m == 2 then "LABU 5 yrs: -41%, 17 trades, 65% won, worst drawdown -76%, up 2 of 5 years. Not a model"
    else if sym == 2 and m == 3 then "LABU 5 yrs: +9% (2%/yr), 61 trades, 59% won, worst drawdown -37%, up 4 of 5 years"
    else if sym == 2 then "LABU 5 yrs: +115% (17%/yr), 32 trades, 63% won, worst drawdown -51%, up 3 of 5 years"
    else if sym == 3 and m == 1 then "DPST 5 yrs: +16% (3%/yr), 71 trades, 68% won, worst drawdown -68%. Buy & hold -75%. Weak"
    else if sym == 3 and m == 2 then "DPST 5 yrs: -72%, 22 trades, 55% won, worst drawdown -82%, up 2 of 5 years. Not a model"
    else if sym == 3 and m == 3 then "DPST 5 yrs: -76%, 76 trades, 53% won, worst drawdown -83%, up 0 of 5 years. Not a model"
    else "DPST 5 yrs: -9%, 30 trades, 57% won, worst drawdown -61%, up 2 of 5 years. Not a model",
    if sym == 1 and m <= 3 then Color.GREEN
    else if (sym == 2 and (m == 1 or m == 4)) then Color.YELLOW
    else if sym == 0 then Color.GRAY
    else Color.RED);

AddLabel(held == 1, "BUY at the close", Color.GREEN);
AddLabel(held > 1, "IN TRADE day " + held + (if m == 4 then "  |  SELL at the close of day 4" else "  |  SELL on a close above " + AsText(exitToday)), Color.CYAN);
AddLabel(held == 0 and held[1] > 0, "SELL at the close", Color.MAGENTA);
AddLabel(held == 0 and held[1] == 0 and !IsNaN(trigToday), "Buy trigger today: a close below " + AsText(trigToday) + " (" + Round((trigToday / c - 1) * 100, 1) + "% from here)", Color.ORANGE);
AddLabel(held == 0 and !IsNaN(trigNext), "Next session: a close below " + AsText(trigNext) + " (" + Round((trigNext / c - 1) * 100, 1) + "% from the latest price)", Color.ORANGE);
