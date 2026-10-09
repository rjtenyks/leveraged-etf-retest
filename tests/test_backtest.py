"""The trade simulator in analyze.py, on a five-day example worked out by hand."""
import datetime as dt
import unittest

from support import load_script

analyze = load_script("analyze")

DAY0 = dt.date(2021, 10, 7)
CLOSES = [10, 11, 9, 12, 12.5]
W = [{"date": DAY0 + dt.timedelta(days=k), "c": c} for k, c in enumerate(CLOSES)]


class Simulate(unittest.TestCase):
    def test_buy_and_hold(self):
        r = analyze.simulate(W, lambda i: i == 0, lambda e, i: False)
        self.assertEqual(r["total"], 24.9)  # 12.5 / 10 x 0.9995 - 1: one cost, never sold
        self.assertEqual((r["trades"], r["exposure"]), (0, 100.0))

    def test_one_round_trip(self):
        # buy at the close of day 1 (11), sell at the close of day 3 (12)
        r = analyze.simulate(W, lambda i: i == 1, lambda e, i: i == 3)
        self.assertEqual(r["trades"], 1)
        self.assertEqual(r["avg_trade"], 8.98)  # 12 / 11 x 0.9995 x 0.9995 - 1
        self.assertEqual(r["win_rate"], 100.0)
        self.assertEqual(r["exposure"], 50.0)  # held over 2 of the 4 days
        self.assertEqual(r["max_dd"], -18.2)  # 11 down to 9, after the entry cost
        self.assertIsNone(r["open_trade"])

    def test_open_trade_reported(self):
        r = analyze.simulate(W, lambda i: i == 2, lambda e, i: False)
        self.assertEqual(r["open_trade"], (str(W[2]["date"]), analyze.pct(12.5 / 9 - 1)))


class Summarize(unittest.TestCase):
    def curve(self, n):
        return [(DAY0 + dt.timedelta(days=k), 1 + k / 100) for k in range(n)]

    def test_keeps_the_final_day(self):
        # The curve is saved every 5th day. An earlier version dropped the final day,
        # which made the README chart's end labels read low ($4.06 instead of $4.34).
        for n in (11, 12, 13, 14, 15):
            c = self.curve(n)
            saved = analyze.summarize(c, 0.0, [], 1.0)["curve"]
            self.assertEqual(saved[-1], (str(c[-1][0]), round(c[-1][1], 4)), n)
            self.assertEqual(len(saved), len(set(saved)), n)  # and doesn't save it twice


if __name__ == "__main__":
    unittest.main()
