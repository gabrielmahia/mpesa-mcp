"""Every tool declares whether it is read-only and whether it is destructive (payments are, queries are not): clients use these hints to decide what is safe to auto-approve.
A tool added later without annotations (or with a wrong one) fails here."""
import asyncio

from fastmcp import Client

from mpesa_mcp import server


def test_every_tool_declares_that_it_is_read_only():
    async def tools():
        async with Client(server.mcp) as c:
            return await c.list_tools()
    ts = asyncio.run(tools())
    assert ts
    for t in ts:
        a = t.annotations
        assert a is not None and a.readOnlyHint is not None and a.destructiveHint is not None, t.name
