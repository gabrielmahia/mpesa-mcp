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
    """Guard against accidental tool loss.

    Asserts a floor rather than an exact count: an exact assertion breaks every
    time a tool is legitimately added (which is how this test came to assert 5
    while the server registered 23), whereas a floor still catches the failure
    that actually matters — tools silently disappearing from registration.
    """
    import asyncio
    from mpesa_mcp import mcp
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) >= 23, f"Tool regression: expected >=23, got {len(tools)}"


def test_normalize_phone():
    """Test phone normalization without network calls."""
    from mpesa_mcp.server import _normalize_phone
    assert _normalize_phone("+254712345678") == "254712345678"
    assert _normalize_phone("0712345678")    == "254712345678"
    assert _normalize_phone("254712345678")  == "254712345678"
    assert _normalize_phone("712345678")     == "254712345678"
