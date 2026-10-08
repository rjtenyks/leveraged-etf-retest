# ============================================================================
# LEV3X_Intraday  -  time-of-day map for SOXL, LABU and DPST
# ----------------------------------------------------------------------------
# Put this on a 5-, 10-, 15- or 30-minute chart of SOXL, LABU or DPST.
# Times are Eastern. What it shows:
#   Gray line     yesterday's close. The first label gives today's opening gap
#                 and how often a gap that size traded back to yesterday's
#                 close the same day (5-year test). It turns green once it has.
#   Blue dashes   the typical dip below today's open: half of all days went at
#                 least as low as the upper line; 1 day in 10 reached the
#                 lower line (5-year test). Useful for sizing a stop.
#   Blue shading  9:30-10:30, the first hour. Together with the overnight gap
#                 it holds most of a day's move. Change its color in the study's
#                 settings under Globals ("First hour").
#   Labels        the fund's opening-gap and late-day patterns, shown only on
#                 days that match, with how they did on hourly prices from
#                 Nov 2023 to Oct 2026 ("3 of 3 years" = same direction in
#                 each year). Historical analysis only, not advice.
# Inputs: fund (AUTO reads the chart symbol), showDipLines, shadeFirstHour.
# ============================================================================
declare upper;

input fund = {default AUTO, SOXL, LABU, DPST};
input showDipLines = yes;
input shadeFirstHour = yes;

def sym = if fund == fund.SOXL then 1 else if fund == fund.LABU then 2 else if fund == fund.DPST then 3
    else if GetSymbol() == "SOXL" then 1 else if GetSymbol() == "LABU" then 2 else if GetSymbol() == "DPST" then 3 else 0;

def rth = SecondsFromTime(930) >= 0 and SecondsTillTime(1600) > 0;
def firstHour = SecondsFromTime(930) >= 0 and SecondsTillTime(1030) > 0;
def lastHalfHour = SecondsFromTime(1530) >= 0 and SecondsTillTime(1600) > 0;

def prevClose = close(period = AggregationPeriod.DAY)[1];
def dayOpen = open(period = AggregationPeriod.DAY);
def gap = dayOpen / prevClose - 1;
def chgNow = close / prevClose - 1;
def filled = if gap < 0 then high(period = AggregationPeriod.DAY) >= prevClose else low(period = AggregationPeriod.DAY) <= prevClose;

# 5-year share of days a gap this size touched yesterday's close before 4:00 pm
def fillPct =
    if sym == 1 then (if gap <= -0.05 then 27 else if gap <= -0.02 then 50 else if gap <= 0 then 83 else if gap < 0.02 then 81 else if gap < 0.05 then 48 else 21)
    else if sym == 2 then (if gap <= -0.05 then 31 else if gap <= -0.02 then 55 else if gap <= 0 then 77 else if gap < 0.02 then 85 else if gap < 0.05 then 50 else 20)
    else if sym == 3 then (if gap <= -0.05 then 25 else if gap <= -0.02 then 46 else if gap <= 0 then 78 else if gap < 0.02 then 82 else if gap < 0.05 then 48 else 24)
    else Double.NaN;
# 5-year drop from the open to the day's low: median and the worst 10% of days
def medDrop = if sym == 1 then -0.030 else if sym == 2 then -0.033 else if sym == 3 then -0.027 else Double.NaN;
def p10Drop = if sym == 1 then -0.090 else if sym == 2 then -0.087 else if sym == 3 then -0.073 else Double.NaN;
# a worst-10% day (Nov 2023 - Oct 2026), and how often its low came after 2:30 pm
def worstDay = if sym == 1 then -0.083 else if sym == 2 then -0.062 else if sym == 3 then -0.049 else Double.NaN;
def lateLowPct = if sym == 1 then 59 else if sym == 2 then 60 else 52;

plot PrevCloseLine = if rth then prevClose else Double.NaN;
PrevCloseLine.SetDefaultColor(Color.GRAY);
PrevCloseLine.SetLineWeight(2);

plot TypicalDip = if showDipLines and rth then dayOpen * (1 + medDrop) else Double.NaN;
TypicalDip.SetDefaultColor(CreateColor(110, 160, 230));
TypicalDip.SetStyle(Curve.SHORT_DASH);

plot DeepDip = if showDipLines and rth then dayOpen * (1 + p10Drop) else Double.NaN;
DeepDip.SetDefaultColor(Color.BLUE);
DeepDip.SetStyle(Curve.SHORT_DASH);

DefineGlobalColor("First hour", CreateColor(35, 75, 130));
AddCloud(if shadeFirstHour and firstHour then Double.POSITIVE_INFINITY else Double.NaN,
         if shadeFirstHour and firstHour then Double.NEGATIVE_INFINITY else Double.NaN,
         GlobalColor("First hour"), GlobalColor("First hour"));

# price at 3:30 pm, as a change from yesterday's close
def chg330 = CompoundValue(1,
    if lastHalfHour and !lastHalfHour[1] then open / prevClose - 1
    else if lastHalfHour then chg330[1]
    else Double.NaN, Double.NaN);

AddLabel(sym == 0, "LEV3X_Intraday: no test for " + GetSymbol() + " (set the fund input)", Color.GRAY);
AddLabel(sym > 0, "Gap " + AsPercent(gap) + "  |  a gap this size went back to yesterday's close on " + fillPct + "% of days"
    + (if filled then "  |  FILLED today" else ""), if filled then Color.GREEN else Color.GRAY);

# opening-gap patterns that held in all 3 years of hourly data
AddLabel(sym == 1 and gap <= -0.05, "SOXL gap down 5%+: from 10:30 to the close these days averaged -1.3% and rose on 42% (3 of 3 years). The first hour averaged +0.9%, mostly in the last year", Color.ORANGE);
AddLabel(sym == 2 and gap >= 0.02, "LABU gap up 2%+: the first hour averaged +0.75% and rose on 60% of days (3 of 3 years)", Color.GREEN);
AddLabel(sym == 2 and AbsValue(gap) < 0.01, "LABU flat open: the first hour averaged -0.50% and rose on 45% of days (3 of 3 years)", Color.ORANGE);
AddLabel(sym == 3 and gap >= 0.02, "DPST gap up 2%+: from 10:30 to the close these days averaged -0.57% and rose on 45% (3 of 3 years)", Color.ORANGE);

# late day
AddLabel(sym == 1 and rth and !lastHalfHour and chgNow >= 0.06, "SOXL up 6%+: if it is still up 6%+ at 3:30, the last 30 minutes have tended to fade", Color.YELLOW);
AddLabel(sym == 1 and chg330 >= 0.06, "SOXL up " + AsPercent(chg330) + " at 3:30: the last 30 min averaged -0.27% and fell on 58% of such days (2 of 3 years); the next open averaged +0.69%", Color.ORANGE);
AddLabel(sym > 0 and rth and chgNow <= worstDay, "Down " + AsPercent(chgNow) + ": on days that closed this badly, the low came after 2:30 pm " + lateLowPct + "% of the time. Early dip-buys were usually early", Color.RED);
