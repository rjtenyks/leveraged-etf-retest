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
                name = h[0].lstrip("# ").split()[0]
                self.assertTrue(path.stem.startswith(name), f"header names {name!r}")
                self.assertGreater(len(h), 3, "header is too short to say what the study does")

    def test_header_lists_every_input(self):
        for path in self.files:
            with self.subTest(path.name):
                text = path.read_text()
                comment = "\n".join(header(text) or [])
                for name in re.findall(r"^input\s+(\w+)\s*=", text, re.M):
                    self.assertRegex(comment, rf"\b{name}\b", f"input {name!r} isn't explained in the header")


if __name__ == "__main__":
    unittest.main()
