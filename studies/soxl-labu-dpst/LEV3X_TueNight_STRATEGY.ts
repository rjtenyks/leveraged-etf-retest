# ============================================================================
# LEV3X_TueNight  -  STRATEGY: buy at Tuesday's close, sell at the next open
# ----------------------------------------------------------------------------
# The "Wednesday" pattern from the study: most of Wednesday's gain came in
# the Tuesday-night gap. Put it on a DAILY chart (time frame 5Y) and use
# Show Report. Buys at Tuesday's 4:00 pm close, sells at Wednesday's open.
# 5-year test (0.05% cost per side, about 257 trades):
#   LABU  +88%, worst drawdown -23%, up in 5 of 5 years (p = 0.07, so it
#         could still be luck)
#   SOXL  +119%, worst drawdown -55%, but almost all of it in the last year
#   DPST  +9%, worst drawdown -49%: no edge
# In Show report each order appears one candle late (thinkorswim books orders
# on the next candle): the buy on Wednesday at Tuesday's close, the sell on
# Thursday at Wednesday's open (same rule as LEV3X_Dip_STRATEGY, which was
# checked; this file was not checked in thinkorswim yet).
# Historical analysis only, not advice. Input: tradeSize (shares).
# ============================================================================
input tradeSize = 100;

def dow = GetDayOfWeek(GetYYYYMMDD());  # 1 = Monday ... 5 = Friday

AddOrder(OrderType.BUY_TO_OPEN, dow == 2, close, tradeSize, Color.GREEN, Color.GREEN, "Tue close");
AddOrder(OrderType.SELL_TO_CLOSE, dow[1] == 2, open, tradeSize, Color.MAGENTA, Color.MAGENTA, "next open");
