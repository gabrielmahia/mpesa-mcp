"""Live-mode outflow tools must be bounded: explicit confirmation, a per-transaction cap, and never a network call when refused."""
import asyncio
import inspect

import pytest
from fastmcp import Client

from mpesa_mcp import server

OUT = {"mpesa_b2c": dict(phone="0712345678", amount=500), "mpesa_business_paybill": dict(receiver_paybill="123456", amount=500, account_reference="A"), "mpesa_business_buygoods": dict(till_number="123456", amount=500),
       "mpesa_business_pochi": dict(phone="0712345678", amount=500), "mpesa_reversal": dict(transaction_id="ABC123", amount=500), "mpesa_tax_remittance": dict(amount=500, account_reference="PRN1"),
       "mpesa_b2b_express_checkout": dict(receiver_till="123456", amount=500, account_reference="A"), "airtime_send": dict(phone="+254712345678", amount=500)}
fn = lambda name: (getattr(server, name).fn if hasattr(getattr(server, name), "fn") else getattr(server, name))  # noqa: E731


class Reached(Exception):
    pass


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setenv("MPESA_SANDBOX", "false")
    monkeypatch.delenv("MPESA_MAX_AMOUNT_KES", raising=False)
    monkeypatch.delenv("MPESA_REQUIRE_CONFIRMATION", raising=False)
    for k in ("MPESA_INITIATOR_NAME", "MPESA_SECURITY_CREDENTIAL", "MPESA_SHORTCODE", "MPESA_RESULT_URL", "MPESA_TIMEOUT_URL", "MPESA_CALLBACK_URL", "MPESA_PASSKEY", "MPESA_CONSUMER_KEY", "MPESA_CONSUMER_SECRET", "AT_API_KEY", "AT_USERNAME"):
        monkeypatch.setenv(k, "x")
    def boom(*a, **k):
        raise Reached("the network was reached")
    monkeypatch.setattr(server.requests, "post", boom)
    monkeypatch.setattr(server.requests, "get", boom)
    monkeypatch.setattr(server, "_get_mpesa_token", lambda: "tok")


@pytest.mark.parametrize("name", sorted(OUT))
def test_live_without_confirmation_is_refused_and_never_reaches_the_network(name, live):
    r = fn(name)(**OUT[name])
    assert r["success"] is False and "Confirmation required" in r["error"] and r["sandbox"] is False


@pytest.mark.parametrize("name", sorted(OUT))
def test_live_with_confirmation_within_the_cap_proceeds_to_the_network(name, live):
    with pytest.raises(Reached):
        fn(name)(**OUT[name], confirm_send=True)


def test_the_default_cap_is_100000_and_exactly_the_cap_is_allowed(live):
    over = fn("mpesa_b2c")(phone="0712345678", amount=100_001, confirm_send=True)
    assert over["success"] is False and "cap of KES 100,000" in over["error"]
    with pytest.raises(Reached):
        fn("mpesa_b2c")(phone="0712345678", amount=100_000, confirm_send=True)


def test_the_cap_is_configurable_and_zero_means_no_cap(live, monkeypatch):
    monkeypatch.setenv("MPESA_MAX_AMOUNT_KES", "1000")
    assert "cap of KES 1,000" in fn("mpesa_b2c")(phone="0712345678", amount=1_001, confirm_send=True)["error"]
    monkeypatch.setenv("MPESA_MAX_AMOUNT_KES", "0")
    with pytest.raises(Reached):
        fn("mpesa_b2c")(phone="0712345678", amount=9_999_999, confirm_send=True)


def test_confirmation_can_be_disabled_only_explicitly(live, monkeypatch):
    monkeypatch.setenv("MPESA_REQUIRE_CONFIRMATION", "false")
    with pytest.raises(Reached):
        fn("mpesa_b2c")(phone="0712345678", amount=500)
    monkeypatch.setenv("MPESA_MAX_AMOUNT_KES", "100")
    assert fn("mpesa_b2c")(phone="0712345678", amount=500)["success"] is False  # the cap still applies


@pytest.mark.parametrize("bad", [0, -5, "abc", None])
def test_live_rejects_non_positive_or_non_numeric_amounts(bad, live):
    assert "positive" in fn("mpesa_b2c")(phone="0712345678", amount=bad, confirm_send=True)["error"]


def test_the_sandbox_is_never_restricted(monkeypatch):
    monkeypatch.setenv("MPESA_SANDBOX", "true")
    assert server._guard("mpesa_b2c", 10_000_000, False) is None


def test_every_outflow_tool_is_guarded_and_advertises_confirm_send():
    for name in OUT:
        assert "_guard(" in inspect.getsource(fn(name)), name
    async def schemas():
        async with Client(server.mcp) as c:
            return {t.name: t.inputSchema for t in await c.list_tools()}
    s = asyncio.run(schemas())
    for name in OUT:
        assert "confirm_send" in s[name]["properties"] and "confirm_send" not in s[name].get("required", []), name
