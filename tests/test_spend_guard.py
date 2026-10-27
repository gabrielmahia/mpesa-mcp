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
    monkeypatch.setenv("MPESA_SESSION_BUDGET_KES", "0")   # this test is about the per-transaction cap, so the aggregate budget is opted out
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


def test_the_session_budget_bounds_the_total_not_just_each_payment(live):
    """100,000 per payment, 300,000 per session by default: the fourth capped payment is refused and never reaches the network."""
    for _ in range(3):
        with pytest.raises(Reached):
            fn("mpesa_b2c")(phone="0712345678", amount=100_000, confirm_send=True)
    r = fn("mpesa_b2c")(phone="0712345678", amount=1, confirm_send=True)
    assert r["success"] is False and "Session budget reached" in r["error"] and "KES 300,000 of its KES 300,000" in r["error"] and "KES 0 left" in r["error"]


def test_the_budget_is_shared_by_every_tool_that_sends_money_out(live):
    with pytest.raises(Reached):
        fn("mpesa_b2c")(phone="0712345678", amount=100_000, confirm_send=True)
    with pytest.raises(Reached):
        fn("mpesa_business_paybill")(receiver_paybill="123456", amount=100_000, account_reference="A", confirm_send=True)
    with pytest.raises(Reached):
        fn("airtime_send")(phone="+254712345678", amount=100_000, confirm_send=True)
    assert "Session budget reached" in fn("mpesa_business_pochi")(phone="0712345678", amount=1, confirm_send=True)["error"]


def test_a_refused_call_does_not_spend_the_budget(live, monkeypatch):
    monkeypatch.setenv("MPESA_SESSION_BUDGET_KES", "1000")
    assert "Confirmation required" in fn("mpesa_b2c")(phone="0712345678", amount=900)["error"]                              # refused: no confirmation
    assert "Session budget reached" in fn("mpesa_b2c")(phone="0712345678", amount=1_500, confirm_send=True)["error"]       # refused: over the whole budget
    with pytest.raises(Reached):
        fn("mpesa_b2c")(phone="0712345678", amount=900, confirm_send=True)                                                 # the whole budget is still there
    assert "KES 100 left" in fn("mpesa_b2c")(phone="0712345678", amount=101, confirm_send=True)["error"]


def test_a_payment_that_exactly_fills_the_budget_is_allowed_and_the_next_is_not(live, monkeypatch):
    monkeypatch.setenv("MPESA_SESSION_BUDGET_KES", "500")
    with pytest.raises(Reached):
        fn("mpesa_b2c")(phone="0712345678", amount=500, confirm_send=True)
    assert "Session budget reached" in fn("mpesa_b2c")(phone="0712345678", amount=1, confirm_send=True)["error"]


@pytest.mark.parametrize("raw", ["0", "none", "unlimited"])
def test_the_budget_can_be_opted_out_only_explicitly(live, monkeypatch, raw):
    monkeypatch.setenv("MPESA_SESSION_BUDGET_KES", raw)
    for _ in range(5):
        with pytest.raises(Reached):
            fn("mpesa_b2c")(phone="0712345678", amount=100_000, confirm_send=True)


def test_an_unparseable_budget_falls_back_to_the_safe_default(live, monkeypatch):
    monkeypatch.setenv("MPESA_SESSION_BUDGET_KES", "lots")
    assert server._session_budget() == server.DEFAULT_LIVE_BUDGET_KES == 300_000


def test_the_sandbox_is_not_subject_to_the_budget(monkeypatch):
    monkeypatch.setenv("MPESA_SANDBOX", "true")
    monkeypatch.setenv("MPESA_SESSION_BUDGET_KES", "1")
    assert server._guard("mpesa_b2c", 10_000_000, False) is None


RECIPIENT_PARAMS = {"mpesa_b2c": "phone", "mpesa_business_paybill": "receiver_paybill", "mpesa_business_buygoods": "till_number", "mpesa_business_pochi": "phone", "mpesa_b2b_express_checkout": "receiver_till", "airtime_send": "phone"}


def _call_args(tool, recipient):
    """Build a valid call for any guarded tool by introspection: the given recipient, KES 500, confirmation, and a harmless value for anything else required."""
    import inspect
    from typing import Annotated, get_args, get_origin
    kwargs = {}
    for p in inspect.signature(fn(tool)).parameters.values():
        if p.name == RECIPIENT_PARAMS[tool]:
            kwargs[p.name] = recipient
        elif p.name == "amount":
            kwargs[p.name] = 500
        elif p.name == "confirm_send":
            kwargs[p.name] = True
        elif p.default is inspect.Parameter.empty:
            base = get_args(p.annotation)[0] if get_origin(p.annotation) is Annotated else p.annotation
            kwargs[p.name] = 1 if base is int else "A1"
    return kwargs


def _listed(tool):
    return "254711111111" if RECIPIENT_PARAMS[tool] == "phone" else "123456"


@pytest.mark.parametrize("tool", sorted(RECIPIENT_PARAMS))
def test_the_recipient_allowlist_covers_every_tool_that_has_a_free_recipient(live, monkeypatch, tool):
    monkeypatch.setenv("MPESA_ALLOWED_RECIPIENTS", _listed(tool))
    other = "0799999999" if RECIPIENT_PARAMS[tool] == "phone" else "999999"
    r = fn(tool)(**_call_args(tool, other))
    assert r["success"] is False and "allowlist" in r["error"], tool
    listed_call = "+254711111111" if tool == "airtime_send" else _listed(tool)   # airtime needs E.164; the leading + must not stop it matching the list
    with pytest.raises(Reached):
        fn(tool)(**_call_args(tool, listed_call))


@pytest.mark.parametrize("fmt", ["0712345678", "+254712345678", "254712345678", "712345678", "0712 345 678", "0712-345-678"])
def test_a_listed_phone_is_recognised_in_any_kenyan_format(live, monkeypatch, fmt):
    monkeypatch.setenv("MPESA_ALLOWED_RECIPIENTS", "254712345678")
    with pytest.raises(Reached):
        fn("mpesa_b2c")(phone=fmt, amount=500, confirm_send=True)


def test_a_refusal_by_the_allowlist_spends_nothing_and_is_recorded(live, monkeypatch):
    monkeypatch.setenv("MPESA_ALLOWED_RECIPIENTS", "0712345678")
    assert "allowlist" in fn("mpesa_b2c")(phone="0799999999", amount=500, confirm_send=True)["error"]
    rep = fn("mpesa_session_report")()
    assert rep["spent_kes"] == 0 and rep["blocked_count"] == 1 and rep["authorised_count"] == 0 and rep["recent"][-1]["outcome"] == "BLOCKED_RECIPIENT_NOT_ALLOWED"


def test_no_allowlist_means_no_restriction_and_a_tool_without_a_free_recipient_is_not_blocked_by_one(live, monkeypatch):
    with pytest.raises(Reached):
        fn("mpesa_b2c")(phone="0799999999", amount=500, confirm_send=True)
    monkeypatch.setenv("MPESA_ALLOWED_RECIPIENTS", "0712345678")
    assert server._guard("mpesa_reversal", 500, True) is None


def test_the_session_report_is_the_servers_own_record_of_what_it_authorised(live, monkeypatch):
    monkeypatch.setenv("MPESA_SESSION_BUDGET_KES", "2000")
    with pytest.raises(Reached):
        fn("mpesa_b2c")(phone="0712345678", amount=500, confirm_send=True)
    rep = fn("mpesa_session_report")()
    assert rep["success"] and rep["limits_apply"] and rep["spent_kes"] == 500 and rep["remaining_kes"] == 1500 and rep["session_budget_kes"] == 2000
    assert rep["authorised_count"] == 1 and rep["blocked_count"] == 0
    last = rep["recent"][-1]
    assert last["tool"] == "mpesa_b2c" and last["outcome"] == "AUTHORISED" and last["amount"] == 500


def test_the_session_report_never_contains_a_full_recipient_number(live):
    with pytest.raises(Reached):
        fn("mpesa_b2c")(phone="0712345678", amount=500, confirm_send=True)
    blob = str(fn("mpesa_session_report")())
    assert "0712345678" not in blob and "254712345678" not in blob and "2547*****678" in blob


def test_spending_is_counted_even_when_the_budget_is_opted_out(live, monkeypatch):
    monkeypatch.setenv("MPESA_SESSION_BUDGET_KES", "0")
    with pytest.raises(Reached):
        fn("mpesa_b2c")(phone="0712345678", amount=500, confirm_send=True)
    rep = fn("mpesa_session_report")()
    assert rep["spent_kes"] == 500 and rep["session_budget_kes"] is None and rep["remaining_kes"] is None


def test_the_session_report_says_when_the_sandbox_is_not_subject_to_limits(monkeypatch):
    monkeypatch.setenv("MPESA_SANDBOX", "true")
    rep = fn("mpesa_session_report")()
    assert rep["sandbox"] is True and rep["limits_apply"] is False
