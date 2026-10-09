"""make_chart.py draws a valid SVG from a small fixture instead of the real results."""
import contextlib
import io
import json
import pathlib
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET

from support import FIXTURES, load_script

make_chart = load_script("make_chart")
SVG = "{http://www.w3.org/2000/svg}"


class Chart(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = FIXTURES / "results_small.json"
        cls.backtests = json.loads(cls.src.read_text())["funds"]["SOXL"]["backtests"]
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "chart.svg"
            make_chart.SRC, make_chart.OUT = cls.src, out
            with contextlib.redirect_stdout(io.StringIO()):
                make_chart.main()
            cls.root = ET.fromstring(out.read_text())  # raises if the SVG isn't well-formed XML
        cls.texts = [t.text for t in cls.root.iter(SVG + "text")]

    def test_is_svg(self):
        self.assertEqual(self.root.tag, SVG + "svg")
        self.assertEqual(self.root.get("viewBox"), f"0 0 {make_chart.W} {make_chart.H}")
        self.assertTrue(self.root.get("aria-label"))

    def test_one_line_per_series(self):
        lines = [p for p in self.root.iter(SVG + "path") if p.get("stroke-width") == "2"]
        self.assertEqual([p.get("stroke") for p in lines], [color for _, _, color in make_chart.SERIES])
        for path, (key, _, _) in zip(lines, make_chart.SERIES):
            self.assertEqual(len(re.findall("[ML]", path.get("d"))), len(self.backtests[key]["curve"]))

    def test_everything_inside_the_frame(self):
        for path in self.root.iter(SVG + "path"):
            for x, y in re.findall(r"([-\d.]+),([-\d.]+)", path.get("d")):
                self.assertTrue(0 <= float(x) <= make_chart.W and 0 <= float(y) <= make_chart.H, path.get("d"))

    def test_end_labels_show_the_final_value(self):
        for key, label, _ in make_chart.SERIES:
            self.assertIn(f"{label} ${self.backtests[key]['curve'][-1][1]:.2f}", self.texts)

    def test_end_labels_dont_overlap(self):
        ends = sorted(float(t.get("y")) for t in self.root.iter(SVG + "text") if "$" in (t.text or "") and t.get("font-size") == "12")
        self.assertEqual(len(ends), len(make_chart.SERIES))
        for a, b in zip(ends, ends[1:]):
            self.assertGreaterEqual(b - a, 16)

    def test_year_marks(self):
        for year in range(2021, 2026):
            self.assertIn(f"Oct {year}", self.texts)


if __name__ == "__main__":
    unittest.main()
