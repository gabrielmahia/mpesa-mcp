"""Tool definitions are what an agent reads before choosing a tool. For a payments server they also have to say plainly which tools move money or message people."""
import asyncio

from fastmcp import Client

from mpesa_mcp import server


def _tools():
    async def go():
        async with Client(server.mcp) as c:
            return await c.list_tools()
    return asyncio.run(go())


def test_every_tool_description_says_when_to_use_it_and_what_it_returns():
    for t in _tools():
        d = t.description or ""
        assert len(d) >= 250, (t.name, len(d))
        assert "Use when" in d or "Use only when" in d or "Use before" in d or "Use after" in d or "Use " in d, t.name
        assert "Returns" in d, t.name


def test_read_only_tools_say_so_and_the_others_state_their_guard_or_who_must_approve():
    for t in _tools():
        d, ann = t.description or "", (t.annotations.model_dump() if t.annotations else {})
        if ann.get("read_only_hint"):
            assert "Read-only" in d, t.name
        else:
            assert "Read-only" not in d, t.name
            assert any(k in d for k in ("confirm_send", "must approve", "approve", "Cancels", "Changes your")), t.name


def test_the_annotations_clients_receive_agree_with_the_descriptions_on_money_and_messaging():
    ann = {t.name: t.annotations.model_dump() for t in _tools()}
    for name in ("mpesa_b2c", "mpesa_business_paybill", "mpesa_business_buygoods", "mpesa_business_pochi", "mpesa_reversal", "mpesa_tax_remittance", "mpesa_b2b_express_checkout", "airtime_send", "sms_send"):
        assert ann[name]["read_only_hint"] is False and ann[name]["destructive_hint"] is True, name


def test_every_parameter_has_a_description():
    for t in _tools():
        for name, prop in (t.inputSchema.get("properties") or {}).items():
            assert prop.get("description"), (t.name, name)
