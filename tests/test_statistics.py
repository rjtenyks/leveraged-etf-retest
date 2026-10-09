"""The hand-written statistics in analyze.py, checked against textbook values."""
import unittest

from support import load_script

analyze = load_script("analyze")


def t_test_p(t, df):
    """Two-sided p-value of Student's t, the way welch_p computes it."""
    return analyze.betainc(df / 2, 0.5, df / (df + t * t))


class IncompleteBeta(unittest.TestCase):
    def test_edges(self):
        self.assertEqual(analyze.betainc(2, 3, 0), 0.0)
        self.assertEqual(analyze.betainc(2, 3, 1), 1.0)

    def test_uniform(self):
        # I_x(1, 1) = x
        self.assertAlmostEqual(analyze.betainc(1, 1, 0.3), 0.3, places=12)

    def test_binomial_identity(self):
        # I_x(2, 3) = P(at least 2 successes in 4 tries with chance x) = 0.5248 at x = 0.4
        self.assertAlmostEqual(analyze.betainc(2, 3, 0.4), 0.5248, places=12)


class StudentT(unittest.TestCase):
    def test_t2_df10(self):
        self.assertAlmostEqual(t_test_p(2.0, 10), 0.07339, places=5)

    def test_critical_value_df10(self):
        # 2.228 is the two-sided 5% critical value for 10 degrees of freedom
        self.assertAlmostEqual(t_test_p(2.228, 10), 0.05, places=4)

    def test_t2_df8(self):
        self.assertAlmostEqual(t_test_p(2.0, 8), 0.08052, places=5)


class Welch(unittest.TestCase):
    def test_end_to_end(self):
        # equal variances 2.5, n = 5 each: t = -2 with 8 degrees of freedom
        self.assertAlmostEqual(analyze.welch_p([1, 2, 3, 4, 5], [3, 4, 5, 6, 7]), 0.08052, places=5)

    def test_symmetric(self):
        a, b = [1.0, 2.5, 3.1, 4.7], [2.2, 3.9, 4.4, 6.0, 6.1]
        self.assertAlmostEqual(analyze.welch_p(a, b), analyze.welch_p(b, a), places=12)

    def test_too_few_or_no_spread(self):
        self.assertIsNone(analyze.welch_p([1, 2], [3, 4, 5]))
        self.assertIsNone(analyze.welch_p([1, 1, 1], [2, 2, 2]))


class Binomial(unittest.TestCase):
    def test_z2(self):
        # 60 heads in 100 fair tosses: z = 2, two-sided p = 0.0455
        self.assertAlmostEqual(analyze.binom_p(60, 100, 0.5), 0.0455, places=4)

    def test_no_tries(self):
        self.assertIsNone(analyze.binom_p(0, 0, 0.5))


class BenjaminiHochberg(unittest.TestCase):
    def test_paper_example(self):
        # The 15 p-values in Benjamini & Hochberg (1995), section 4: the method rejects 4 at q = 0.05
        ps = [0.0001, 0.0004, 0.0019, 0.0095, 0.0201, 0.0278, 0.0298, 0.0344, 0.0459,
              0.3240, 0.4262, 0.5719, 0.6528, 0.7590, 1.000]
        q = analyze.bh_qvalues(ps)
        self.assertEqual(sum(x <= 0.05 for x in q), 4)
        self.assertAlmostEqual(q[3], 0.035625, places=6)  # 0.0095 x 15 / 4
        self.assertAlmostEqual(q[4], 0.0603, places=6)  # 0.0201 x 15 / 5, just above the line

    def test_keeps_input_order(self):
        q = analyze.bh_qvalues([0.01, 0.04, 0.03, 0.005])
        for got, want in zip(q, [0.02, 0.04, 0.04, 0.02]):
            self.assertAlmostEqual(got, want, places=12)


class Indicators(unittest.TestCase):
    def test_wilder_rsi(self):
        rsi = analyze.wilder_rsi([10, 11, 12, 11, 13], 2)
        self.assertEqual(rsi[:2], [None, None])
        self.assertEqual(rsi[2], 100.0)  # two up days, no losses yet
        # day 3: gains (1 + 0) / 2 = 0.5, losses (0 + 1) / 2 = 0.5, so RSI 50; day 4: 1.25 vs 0.25, RSI 83.3
        self.assertAlmostEqual(rsi[3], 50.0, places=9)
        self.assertAlmostEqual(rsi[4], 100 - 100 / 6, places=9)


if __name__ == "__main__":
    unittest.main()
