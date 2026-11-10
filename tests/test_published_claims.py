"""What the project says about itself must match what it does: tool counts in every published description, and the confirmation default in the docs agents read."""
import asyncio
import json
import re
from pathlib import Path

from fastmcp import Client

from mpesa_mcp import confirm, server

ROOT = Path(__file__).resolve().parents[1]


def _real_tool_count() -> int:
    async def n():
        async with Client(server.mcp) as c:
            return len(await c.list_tools())
    return asyncio.run(n())


def test_every_published_tool_count_matches_the_real_one():
    real = _real_tool_count()
    texts = {"pyproject.toml": (ROOT / "pyproject.toml").read_text(encoding="utf-8")}
    for name in ("agent-context.json", "server.json", "glama.json"):
        texts[name] = json.dumps(json.loads((ROOT / name).read_text(encoding="utf-8")))
    stated = {name: {int(m) for m in re.findall(r"\b(\d+) tools\b", t)} for name, t in texts.items()}
    wrong = {name: sorted(s) for name, s in stated.items() if s and s != {real}}
    assert not wrong, f"the server has {real} tools; these files say otherwise: {wrong}"
    assert all(stated.values()), f"a metadata file no longer states a tool count: {stated}"


def test_the_docs_agents_read_state_the_fail_closed_default():
    assert confirm.confirm_mode() in ("elicit", "auto", "param")
    for name in ("AGENTS.md", "README.md"):
        t = (ROOT / name).read_text(encoding="utf-8")
        assert "default `auto`" not in t and "`auto` (default" not in t, f"{name} still calls auto the default"
        assert "elicit" in t and "refuse" in t.lower(), f"{name} must say that the default refuses without a person's confirmation"
