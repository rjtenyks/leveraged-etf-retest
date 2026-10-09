"""MCP server: questions about the 5-year SOXL · LABU · DPST retest, answered from the saved results.

Three read-only tools, each a thin wrapper around results.py. It serves over stdio, and Claude Code in
this folder starts it from .mcp.json. Run by hand, it waits for an MCP client on stdin:
  .venv/bin/python mcp_server/server.py
Needs the mcp package from requirements.txt (see the README). The results come from analyze.py.
"""
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

import results

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)

server = MCPServer(
    "leveraged-etf-retest",
    instructions=(
        "Results of a 5-year retest of trading rules and patterns on three 3x leveraged ETFs: SOXL "
        "(semiconductors), LABU (biotech) and DPST (regional banks). The tools give the exact window. Returns "
        "are percent; each rule says how it trades and what it costs. Quote the numbers the tools return "
        "instead of estimating. This is historical analysis, not investment advice."
    ),
)


def answer(question, *args):
    """Call a results.py function. A question it can't answer becomes a ToolError, the one exception whose
    message the SDK passes on to the client; any other reaches it only as "Error executing tool ...".
    The tools return dict[str, Any] rather than dict because only that form gets structured output."""
    try:
        return question(*args)
    except results.ResultsError as e:
        raise ToolError(str(e)) from None


@server.tool(annotations=READ_ONLY)
def get_results(fund: str) -> dict[str, Any]:
    """Every trading rule tested on one fund (SOXL, LABU or DPST), best 5-year total return first.

    For each rule: how it trades and its costs, total return, CAGR, worst drawdown, the return in each
    12-month year (October to October) and how many were up, trades, win rate, average trade, time in the
    market, and any trade still open at the end. Buy & hold is included for comparison.
    """
    return answer(results.get_results, fund)


@server.tool(annotations=READ_ONLY)
def compare_funds(rule: str) -> dict[str, Any]:
    """One trading rule on all three funds, side by side.

    `rule` is matched loosely against the rule names, for example "RSI(2)", "Bollinger", "3 down days",
    "Tuesday" or "buy and hold". Every matching rule is returned, closest first; check the rule names.
    An unknown rule returns the list of rule names.
    """
    return answer(results.compare_funds, rule)


@server.tool(annotations=READ_ONLY)
def pattern_verdict(query: str = "", fund: str | None = None) -> dict[str, Any]:
    """Did a pattern hold up? Searches all the pattern tests by name, smallest p-value first.

    The tests cover signals (such as "RSI(2) below 10" or "after a 2-sigma drop"), weekdays, FOMC days,
    calendar effects, VIX levels, opening gaps and the last 30 minutes. Each match has its p-value, its
    q-value after the Benjamini-Hochberg false-discovery check across all the tests, and a verdict:
    "held up" (q < 0.10), "probably luck" (p < 0.05 on its own) or "no evidence". The summary counts the
    tests in scope. Leave `query` empty to list the strongest results; set `fund` to SOXL, LABU or DPST
    to narrow the search.
    """
    return answer(results.pattern_verdict, query, fund)


if __name__ == "__main__":
    server.run()
