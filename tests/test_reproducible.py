"""backtests/soxl-labu-dpst/check_reproducible.py, run against tiny stand-ins for analyze.py and make_chart.py.

The real scripts need the downloaded prices, which aren't in the repo. Each test copies the real check
into a throwaway project next to two stand-ins with the same paths, then sets up one situation.
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import SCRIPTS

ANALYZE = '''import pathlib
RAW = pathlib.Path("data/soxl-labu-dpst/raw")
OUT = pathlib.Path("data/soxl-labu-dpst/results_5y.json")
if __name__ == "__main__":
    prices = (RAW / "prices.txt").read_text()
    if prices == "crash":
        raise SystemExit("bad prices")
    if prices == "hang":
        import time
        time.sleep(30)
    OUT.write_text("results of " + prices)
'''
MAKE_CHART = '''import pathlib
SRC = pathlib.Path("data/soxl-labu-dpst/results_5y.json")
OUT = pathlib.Path("docs/images/soxl-growth-5y.svg")
if __name__ == "__main__":
    OUT.write_text("<svg>" + SRC.read_text() + "</svg>")
'''


class CheckReproducible(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = pathlib.Path(self.tmp.name)
        scripts = self.project / "backtests" / "soxl-labu-dpst"
        scripts.mkdir(parents=True)
        shutil.copy(SCRIPTS / "check_reproducible.py", scripts)
        (scripts / "analyze.py").write_text(ANALYZE)
        (scripts / "make_chart.py").write_text(MAKE_CHART)
        self.raw = self.project / "data" / "soxl-labu-dpst" / "raw"
        self.raw.mkdir(parents=True)
        (self.raw / "prices.txt").write_text("p1")
        self.results = self.project / "data" / "soxl-labu-dpst" / "results_5y.json"
        self.results.write_text("results of p1")
        self.chart = self.project / "docs" / "images" / "soxl-growth-5y.svg"
        self.chart.parent.mkdir(parents=True)
        self.chart.write_text("<svg>results of p1</svg>")

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, cwd=None, **env):
        """Run the check; return its exit code and output."""
        script = self.project / "backtests" / "soxl-labu-dpst" / "check_reproducible.py"
        p = subprocess.run([sys.executable, str(script)], cwd=cwd or self.project, capture_output=True, text=True,
                           env=dict(os.environ, **env), timeout=60)
        return p.returncode, p.stdout

    def test_match(self):
        code, out = self.check()
        self.assertEqual(code, 0)
        self.assertIn("Reproducible", out)

    def test_runs_from_any_folder(self):
        elsewhere = self.project / "elsewhere"
        elsewhere.mkdir()
        self.assertEqual(self.check(cwd=elsewhere)[0], 0)

    def test_results_differ(self):
        (self.raw / "prices.txt").write_text("p2")
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("DIFFERS: analyze.py gives different results", out)
        self.assertNotIn("make_chart.py draws", out)  # the chart is drawn from the saved results

    def test_chart_differs(self):
        self.chart.write_text("<svg>old</svg>")
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("DIFFERS: make_chart.py draws a different chart", out)
        self.assertIn("If only the prices differ", out)
        self.assertNotIn("analyze.py gives", out)

    def test_analysis_crashes(self):
        (self.raw / "prices.txt").write_text("crash")
        code, out = self.check()
        self.assertEqual(code, 3)
        self.assertIn("analyze.py failed", out)
        self.assertIn("bad prices", out)

    def test_analysis_hangs(self):
        (self.raw / "prices.txt").write_text("hang")
        code, out = self.check(CHECK_REPRODUCIBLE_TIMEOUT="1")
        self.assertEqual(code, 3)
        self.assertIn("analyze.py didn't finish within 1 s", out)

    def test_broken_script(self):
        (self.project / "backtests" / "soxl-labu-dpst" / "analyze.py").write_text("def broken(:\n")
        code, out = self.check()
        self.assertEqual(code, 3)
        self.assertIn("Can't import", out)

    def test_no_prices(self):
        shutil.rmtree(self.raw)
        code, out = self.check()
        self.assertEqual(code, 2)
        self.assertIn("No downloaded prices", out)

    def test_no_saved_results(self):
        self.results.unlink()
        code, out = self.check()
        self.assertEqual(code, 2)
        self.assertIn("No saved results", out)
        self.assertNotIn("downloaded prices", out)


if __name__ == "__main__":
    unittest.main()
