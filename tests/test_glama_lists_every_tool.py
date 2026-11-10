"""glama.json is what Glama builds the listing from. It claimed 24 tools while naming 23 (mpesa_session_report, the tool for verifying what the server
authorised, was missing). It must always name exactly the tools the server exposes."""
import asyncio
import json
from pathlib import Path

from fastmcp import Client

from mpesa_mcp import server


def test_glama_json_names_exactly_the_tools_the_server_exposes():
    async def names():
        async with Client(server.mcp) as c:
            return {t.name for t in await c.list_tools()}
    exposed = asyncio.run(names())
    listed = {t["name"] if isinstance(t, dict) else t for t in json.loads((Path(__file__).parents[1] / "glama.json").read_text(encoding="utf-8"))["tools"]}
    assert listed == exposed, f"missing from glama.json: {sorted(exposed - listed)}; not in server: {sorted(listed - exposed)}"
