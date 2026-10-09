"""The CI workflow and the branch protection settings agree.

Branch protection requires a check by its name. If the job it names is renamed or removed from the
workflow, every pull request waits forever for a check that never comes, the admin's included. The
settings live in .github/branch-protection.json; GitHub uses them only once they're applied with
  gh api -X PUT repos/rjtenyks/leveraged-etf-retest/branches/main/protection --input .github/branch-protection.json
"""
import json
import re
import unittest

from support import ROOT

WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"
PROTECTION = ROOT / ".github" / "branch-protection.json"
GITHUB_ACTIONS = 15368  # the GitHub app that reports workflow jobs


def job(name):
    """The text of one job in the workflow, or None. (The standard library has no YAML parser.)"""
    m = re.search(rf"^  {re.escape(name)}:\n((?:    .*\n|[ \t]*\n)*)", WORKFLOW.read_text(), re.M)
    return m.group(1) if m else None


class BranchProtection(unittest.TestCase):
    def setUp(self):
        self.settings = json.loads(PROTECTION.read_text())

    def test_requires_only_the_summary_job(self):
        checks = self.settings["required_status_checks"]["checks"]
        self.assertEqual(checks, [{"context": "tests-passed", "app_id": GITHUB_ACTIONS}])

    def test_the_required_job_exists_and_waits_for_the_tests(self):
        self.assertIsNotNone(job("unittest"))
        for check in self.settings["required_status_checks"]["checks"]:
            text = job(check["context"])
            self.assertIsNotNone(text, f"branch protection requires {check['context']!r}, but tests.yml has no such job")
            self.assertIn("needs: unittest", text)
            self.assertIn("if: always()", text)  # without it, a failed unittest skips this job, and skipped counts as passed
            self.assertIn('test "$RESULT" = success', text)
            self.assertIn("RESULT: ${{ needs.unittest.result }}", text)

    def test_the_rules_hold_for_everyone(self):
        s = self.settings
        self.assertTrue(s["required_status_checks"]["strict"])  # up to date with main before merging
        self.assertTrue(s["enforce_admins"])
        self.assertIsNotNone(s["required_pull_request_reviews"])  # changes arrive only through pull requests
        self.assertFalse(s["allow_force_pushes"])
        self.assertFalse(s["allow_deletions"])


if __name__ == "__main__":
    unittest.main()
