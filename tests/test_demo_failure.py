"""DEMONSTRATION ONLY, never merged: a test that fails on purpose.

It shows that branch protection on main refuses a pull request whose tests fail (see #5 and #6).
"""
import unittest


class DeliberateFailure(unittest.TestCase):
    def test_fails_on_purpose(self):
        self.assertEqual(1 + 1, 3, "this test is broken on purpose, to show the merge being blocked")


if __name__ == "__main__":
    unittest.main()
