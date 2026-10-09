"""Every thinkScript file opens with a header comment that names it and explains its inputs."""
import re
import unittest

from support import STUDIES

RULE = re.compile(r"^# ={20,}$")


def header(text):
    """The comment block between the two '# =====' rules at the top of the file, or None."""
    lines = text.splitlines()
    if not lines or not RULE.match(lines[0]):
        return None
    for k, line in enumerate(lines[1:], 1):
        if RULE.match(line):
            return lines[1:k]
        if not line.startswith("#"):
            return None
    return None


class StudyHeaders(unittest.TestCase):
    files = sorted(STUDIES.glob("*.ts"))

    def test_files_found(self):
        self.assertGreaterEqual(len(self.files), 5)

    def test_header_names_the_study(self):
        for path in self.files:
            with self.subTest(path.name):
                h = header(path.read_text())
                self.assertIsNotNone(h, "no '# ====' header block at the top")
                self.assertGreater(len(h), 3, "header is too short to say what the study does")
                words = h[0].lstrip("# ").split()
                self.assertTrue(words, "the header's first line should name the study")
                # the full name, or the family name when the file adds its type (LEV3X_Dip -> LEV3X_Dip_STUDY)
                self.assertIn(path.stem, [words[0] + s for s in ("", "_STUDY", "_STRATEGY", "_COLUMN")],
                              f"header names {words[0]!r}")

    def test_header_lists_every_input(self):
        for path in self.files:
            with self.subTest(path.name):
                text = path.read_text()
                names = re.findall(r"^\s*input\s+(\w+)\s*=", text, re.M | re.I)  # thinkScript ignores case
                if not names:
                    continue
                listed = re.search(r"\bInputs?:(.*)", "\n".join(header(text) or []), re.S)
                self.assertIsNotNone(listed, "the header has no 'Inputs:' line")
                for name in names:
                    self.assertRegex(listed.group(1), rf"\b{name}\b", f"input {name!r} isn't on the header's 'Inputs:' line")


if __name__ == "__main__":
    unittest.main()
