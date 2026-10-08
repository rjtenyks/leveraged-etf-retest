# ============================================================================
# LEV3X_Dip_COLUMN  -  watchlist column for the RSI(2) dip model
# Add SOXL, LABU and DPST to a watchlist, create a custom column with this
# code and set the column's aggregation to D (day). Each row shows BUY / SELL /
# HOLD for the RSI2_DIP model, or the RSI(2), today's buy trigger (buy<) and
# the next session's (nxt<, from the latest price). Widen the column to read it.
# Green = buy at the close, magenta = sell at the close, cyan = in a trade,
# yellow = RSI(2) under 20. DPST shows gray: the model had no edge there in
# the 5-year test (+16% with a -68% drawdown).
# ============================================================================
def sym = if GetSymbol() == "SOXL" then 1 else if GetSymbol() == "LABU" then 2 else if GetSymbol() == "DPST" then 3 else 0;
def c = close;
def chg = c - c[1];
def avgUp = WildersAverage(Max(chg, 0), 2);
def avgDn = WildersAverage(Max(-chg, 0), 2);
def rsi2 = if avgDn == 0 then 100 else 100 - 100 / (1 + avgUp / avgDn);
def held = CompoundValue(1,
    if held[1] == 0 then (if rsi2 < 10 then 1 else 0)
    else if c > Average(c, 5) or held[1] >= 10 then 0
    else held[1] + 1, 0);
# close below this today pushes RSI(2) under 10 (9 = (100 - 10) / 10)
def trigToday = if 9 * avgUp[1] >= avgDn[1] then c[1] - (9 * avgUp[1] - avgDn[1]) else c[1] + (avgDn[1] / 9 - avgUp[1]);
def trigNext = if 9 * avgUp >= avgDn then c - (9 * avgUp - avgDn) else c + (avgDn / 9 - avgUp);

plot S = rsi2;
AddLabel(yes,
    if sym == 3 then "RSI " + Round(rsi2, 0) + " no edge"
    else if held == 1 then "BUY at close"
    else if held == 0 and held[1] > 0 then "SELL at close"
    else if held > 1 then "HOLD d" + held + " exit>" + Round(Average(c, 4)[1], 2)
    else "RSI " + Round(rsi2, 0) + " buy<" + Round(trigToday, 2) + " nxt<" + Round(trigNext, 2),
    Color.BLACK);
AssignBackgroundColor(
    if sym == 3 then Color.LIGHT_GRAY
    else if held == 1 then Color.GREEN
    else if held == 0 and held[1] > 0 then Color.MAGENTA
    else if held > 1 then Color.CYAN
    else if rsi2 < 20 then Color.YELLOW
    else Color.LIGHT_GRAY);
