"""The MCP server (mcp_server/server.py), spoken to over the MCP protocol by the SDK's own client.

Needs the mcp package from requirements.txt, and skips without it. CI installs it; locally, run the
tests with the project's environment:  .venv/bin/python -m unittest discover -s tests
"""
import contextlib
import importlib.util
import json
import logging
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

from support import MCP_SERVER
from test_mcp_tools import FIXTURE

HAVE_MCP = importlib.util.find_spec("mcp") is not None
SKIP = "needs the mcp package: .venv/bin/pip install --require-hashes -r requirements.txt"


class WithFixture(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # IsolatedAsyncioTestCase runs asyncio in debug mode, which logs every step slower than 0.1 s and
        # every subprocess; that noise would reach Claude through the hook. Real problems still fail the tests.
        asyncio_log = logging.getLogger("asyncio")
        self.addCleanup(asyncio_log.setLevel, asyncio_log.level)
        asyncio_log.setLevel(logging.ERROR)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = pathlib.Path(tmp.name) / "results_5y.json"
        self.path.write_text(json.dumps(FIXTURE))


@unittest.skipUnless(HAVE_MCP, SKIP)
class InProcess(WithFixture):
    @contextlib.asynccontextmanager
    async def connect(self):
        """A client connected to the server in this process. Each test opens its own: the SDK's task groups
        must be entered and left in the same task, and asyncSetUp and the cleanups run in different ones."""
        import results
        import server
        from mcp import Client
        sdk_log = logging.getLogger("mcp")
        level = sdk_log.level
        sdk_log.setLevel(logging.CRITICAL)  # the SDK logs each tool error; the tests check them instead
        try:
            with mock.patch.object(results, "RESULTS", self.path):
                async with Client(server.server) as client:
                    yield client
        finally:
            sdk_log.setLevel(level)

    async def test_three_read_only_tools(self):
        async with self.connect() as client:
            tools = {t.name: t for t in (await client.list_tools()).tools}
        self.assertEqual(sorted(tools), ["compare_funds", "get_results", "pattern_verdict"])
        for t in tools.values():
            with self.subTest(t.name):
                self.assertTrue(t.annotations.read_only_hint)
                self.assertFalse(t.annotations.open_world_hint)
                self.assertGreater(len(t.description), 80)  # the model picks tools by their descriptions
                self.assertEqual(t.output_schema["type"], "object")  # structured output is on
        self.assertEqual(tools["get_results"].input_schema["required"], ["fund"])
        self.assertEqual(tools["compare_funds"].input_schema["required"], ["rule"])
        self.assertNotIn("required", tools["pattern_verdict"].input_schema)  # both arguments are optional

    async def test_answers_match_results_py(self):
        import results
        cases = (("get_results", {"fund": "labu"}, lambda: results.get_results("labu")),
                 ("compare_funds", {"rule": "3 down days"}, lambda: results.compare_funds("3 down days")),
                 ("pattern_verdict", {"query": "fomc", "fund": "SOXL"}, lambda: results.pattern_verdict("fomc", "SOXL")),
                 ("pattern_verdict", {}, lambda: results.pattern_verdict()))
        async with self.connect() as client:
            for tool, args, direct in cases:
                with self.subTest(tool=tool, args=args):
                    out = await client.call_tool(tool, args)
                    self.assertFalse(out.is_error, out.content)
                    self.assertEqual(out.structured_content, direct())
                    self.assertEqual(json.loads(out.content[0].text), direct())  # clients without structured output get JSON text

    async def test_questions_it_cant_answer_are_tool_errors(self):
        cases = (("get_results", {"fund": "TQQQ"}, "Unknown fund 'TQQQ'. The retest covers SOXL, LABU, DPST only."),
                 ("compare_funds", {"rule": "moon phase"}, "No rule matches 'moon phase'. The rules are: Buy & hold;"),
                 ("pattern_verdict", {"query": "moon"}, "No pattern test matches 'moon'."))
        async with self.connect() as client:
            for tool, args, message in cases:
                with self.subTest(tool):
                    out = await client.call_tool(tool, args)
                    self.assertTrue(out.is_error)
                    self.assertIn(message, out.content[0].text)  # the SDK puts "Error executing tool ...:" in front

    async def test_missing_results_say_how_to_make_them(self):
        self.path.unlink()
        async with self.connect() as client:
            out = await client.call_tool("get_results", {"fund": "SOXL"})
        self.assertTrue(out.is_error)
        self.assertIn("fetch_prices.py, then analyze.py", out.content[0].text)


class Installed(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("CI"), "only in CI, where requirements.txt is installed")
    def test_ci_has_the_mcp_package(self):
        self.assertTrue(HAVE_MCP, "CI must install requirements.txt, or the MCP server tests silently skip")


@unittest.skipUnless(HAVE_MCP, SKIP)
class OverStdio(WithFixture):
    """The way Claude Code runs it (.mcp.json): server.py as its own process, talking over stdin and stdout."""

    async def test_launch_list_and_call(self):
        from mcp import Client, StdioServerParameters
        params = StdioServerParameters(command=sys.executable, args=[str(MCP_SERVER / "server.py")],
                                       env=dict(os.environ, LETF_RESULTS=str(self.path)))
        async with Client(params, read_timeout_seconds=30) as client:
            self.assertEqual(client.server_info.name, "leveraged-etf-retest")
            self.assertIn("not investment advice", client.instructions)
            self.assertEqual(len((await client.list_tools()).tools), 3)
            out = await client.call_tool("compare_funds", {"rule": "buy and hold"})
        self.assertFalse(out.is_error, out.content)
        self.assertEqual(out.structured_content["rules"][0]["funds"]["SOXL"]["total_return_pct"], 100.0)


if __name__ == "__main__":
    unittest.main()
