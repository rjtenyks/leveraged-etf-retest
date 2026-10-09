"""make_chart.py draws a correct SVG from a small fixture instead of the real results."""
import contextlib
import io
import json
import math
import pathlib
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET

from support import FIXTURES
import make_chart as mc

SVG = "{http://www.w3.org/2000/svg}"
PLOT_LEFT, PLOT_RIGHT, PLOT_TOP, PLOT_BOTTOM = mc.L, mc.W - mc.R, mc.T, mc.H - mc.B


def points(path):
    return [(float(x), float(y)) for x, y in re.findall(r"([-\d.]+),([-\d.]+)", path.get("d"))]


class Chart(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src = FIXTURES / "results_small.json"
        cls.backtests = json.loads(src.read_text())["funds"]["SOXL"]["backtests"]
        cls.dates = [d for d, _ in cls.backtests[mc.SERIES[0][0]]["curve"]]
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "chart.svg"
            with contextlib.redirect_stdout(io.StringIO()):
                mc.main(src, out)
            cls.root = ET.fromstring(out.read_text())  # raises if the SVG isn't well-formed XML
        cls.texts = list(cls.root.iter(SVG + "text"))
        cls.lines = [p for p in cls.root.iter(SVG + "path") if p.get("stroke-width") == "2"]

    def x_of(self, i):
        return PLOT_LEFT + (PLOT_RIGHT - PLOT_LEFT) * i / (len(self.dates) - 1)

    def test_is_svg(self):
        self.assertEqual(self.root.tag, SVG + "svg")
        self.assertEqual(self.root.get("viewBox"), f"0 0 {mc.W} {mc.H}")
        self.assertTrue(self.root.get("aria-label"))

    def test_one_line_per_series(self):
        self.assertEqual([p.get("stroke") for p in self.lines], [color for _, _, color in mc.SERIES])
        for path, (key, _, _) in zip(self.lines, mc.SERIES):
            self.assertEqual(len(points(path)), len(self.backtests[key]["curve"]))

    def test_higher_values_drawn_higher(self):
        # log scale: equal ratios are equal heights, and a bigger value has a smaller y (SVG y grows downward)
        drawn = sorted((v, y) for path, (key, _, _) in zip(self.lines, mc.SERIES)
                       for (_, v), (_, y) in zip(self.backtests[key]["curve"], points(path)))
        for (v1, y1), (v2, y2) in zip(drawn, drawn[1:]):
            if v2 > v1:
                self.assertLess(y2, y1, (v1, v2))
        (va, ya), (vb, yb), (vc, yc) = drawn[0], drawn[len(drawn) // 2], drawn[-1]
        self.assertAlmostEqual((ya - yb) / (yb - yc), math.log(vb / va) / math.log(vc / vb), places=1)

    def test_lines_inside_the_plot_with_a_margin(self):
        for path in self.lines:
            for x, y in points(path):
                self.assertTrue(PLOT_LEFT <= x <= PLOT_RIGHT, x)
                self.assertTrue(PLOT_TOP < y < PLOT_BOTTOM, y)  # padded: the extremes don't touch the frame

    def test_gridlines_and_labels_inside(self):
        for line in self.root.iter(SVG + "line"):
            for y in (float(line.get("y1")), float(line.get("y2"))):
                self.assertTrue(PLOT_TOP <= y <= PLOT_BOTTOM, y)
        for t in self.texts:
            self.assertTrue(0 <= float(t.get("x")) <= mc.W and 0 <= float(t.get("y")) <= mc.H, t.text)

    def test_one_dollar_gridline_matches_the_data(self):
        start = points(self.lines[1])[0][1]  # the RSI(2) line starts at exactly $1.00 in the fixture
        label = next(t for t in self.texts if t.text == "$1")
        self.assertAlmostEqual(float(label.get("y")) - 4, start, delta=0.1)

    def test_end_labels_show_the_final_value(self):
        shown = [t.text for t in self.texts]
        for key, label, _ in mc.SERIES:
            self.assertIn(f"{label} ${self.backtests[key]['curve'][-1][1]:.2f}", shown)

    def test_end_labels_dont_overlap(self):
        ends = sorted(float(t.get("y")) for t in self.texts if "$" in (t.text or "") and t.get("font-size") == "12")
        self.assertEqual(len(ends), len(mc.SERIES))
        for a, b in zip(ends, ends[1:]):
            self.assertGreaterEqual(b - a, 16)

    def test_year_marks_at_the_right_date(self):
        for year in range(2022, 2026):
            i = next(k for k, d in enumerate(self.dates) if d >= f"{year}-10-07")
            label = next(t for t in self.texts if t.text == f"Oct {year}")
            self.assertAlmostEqual(float(label.get("x")), self.x_of(i), delta=0.1)


if __name__ == "__main__":
    unittest.main()
