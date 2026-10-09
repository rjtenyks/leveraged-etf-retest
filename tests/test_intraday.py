"""The worst-10% cutoff analyze.py saves for the intraday study, on 21 made-up hourly days.

The study (studies/soxl-labu-dpst/LEV3X_Intraday_STUDY.ts) hard-codes each fund's worst-10% day. The last class
checks those constants against the saved results, and skips without them.
"""
import datetime as dt
import re
import unittest

from support import STUDIES
import analyze
from test_mcp_tools import NEEDS_RESULTS, have_results
import results

# 21 days; analyze.quantile(x, 0.10) takes the 3rd smallest of 21 (index round(0.1 x 20) = 2).
RETS = [-0.09, -0.07, -0.04949889] + [k / 100 - 0.02 for k in range(18)]


def day(k, ret):
    """One made-up day: a move of `ret` from a prior close of 100, spread evenly over the 8 parts of the day."""
    seg = (1 + ret) ** (1 / 8) - 1
    return {"date": dt.date(2024, 1, 2) + dt.timedelta(days=k), "ret": ret, "gap": seg, "segs": [seg] * 8, "low_bar": k % 7,
            "pc": 100.0, "c": 100 * (1 + ret), "p1030": 100 * (1 + seg) ** 2, "p330": 100 * (1 + seg) ** 7, "nxt_gap": 0.0}


class WorstTenPercentCutoff(unittest.TestCase):
    def test_the_10_percent_quantile_to_4_decimals(self):
        out = analyze.intraday("TEST", [day(k, r) for k, r in enumerate(RETS)])
        self.assertEqual(out["worst10_cutoff"], -4.9499)  # -4.949889%: 2 decimals would give -4.95, which reads as -0.050
        self.assertEqual(out["days"], 21)


@unittest.skipUnless(have_results(), NEEDS_RESULTS)
class StudyConstants(unittest.TestCase):
    def test_worst_day_constants_match_the_results(self):
        line = next(l for l in (STUDIES / "LEV3X_Intraday_STUDY.ts").read_text().splitlines() if l.startswith("def worstDay"))
        constants = {int(sym): float(v) for sym, v in re.findall(r"sym == (\d) then (-?[\d.]+)", line)}
        data = results.load()["funds"]
        for sym, fund in ((1, "SOXL"), (2, "LABU"), (3, "DPST")):  # the study's numbering
            with self.subTest(fund):
                self.assertEqual(round(data[fund]["intraday"]["worst10_cutoff"] / 100, 3), constants[sym])


if __name__ == "__main__":
    unittest.main()
