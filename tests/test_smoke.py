"""Smoke tests — verify imports and tool registration without live API calls."""

import os
import sys

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_import():
    from mpesa_mcp import mcp
    assert mcp is not None


def test_tools_registered():
    import asyncio
    from mpesa_mcp import mcp
    tools = asyncio.run(mcp.list_tools())
    names = [t.name for t in tools]
    expected = [
        "mpesa_stk_push",
        "mpesa_stk_query",
        "mpesa_transaction_status",
        "sms_send",
        "airtime_send",
    ]
    for name in expected:
        assert name in names, f"Tool '{name}' not registered. Found: {names}"


def test_tool_count():
    import asyncio
    from mpesa_mcp import mcp
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 5, f"Expected 5 tools, got {len(tools)}"


def test_normalize_phone():
    """Test phone normalization without network calls."""
    from mpesa_mcp.server import _normalize_phone
    assert _normalize_phone("+254712345678") == "254712345678"
    assert _normalize_phone("0712345678")    == "254712345678"
    assert _normalize_phone("254712345678")  == "254712345678"
    assert _normalize_phone("712345678")     == "254712345678"
