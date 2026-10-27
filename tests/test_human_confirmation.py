"""The person, not the model, confirms each payment: MCP elicitation through a middleware, in both protocol eras."""
import asyncio
import inspect
import re
import time
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.elicitation import ElicitResult
from fastmcp.server.elicitation import (
    AcceptedElicitation,
    CancelledElicitation,
    DeclinedElicitation,
)
from helpers import Reached, fn

from mpesa_mcp import confirm, server

SRC = Path(__file__).resolve().parents[1] / "src" / "mpesa_mcp" / "server.py"
PAY = {"phone": "0712345678", "amount": 500}


@pytest.fixture
def net(live, monkeypatch):
    """Counts every network call; each one raises Reached so a payment 'runs' without a real network."""
    hits = []

    def boom(*a, **k):
        hits.append(1)
        raise Reached("the network was reached")
    monkeypatch.setattr(server.requests, "post", boom)
    monkeypatch.setattr(server.requests, "get", boom)
    return hits


async def _call(tool, args, handler=None):
    client = Client(server.mcp, elicitation_handler=handler) if handler else Client(server.mcp)
    async with client as c:
        return await c.call_tool(tool, args, raise_on_error=False)


def call(tool, args, handler=None):
    return asyncio.run(_call(tool, args, handler))


def text(result):
    return " ".join(getattr(b, "text", "") for b in result.content) + " " + str(getattr(result, "structured_content", None))


def approving(prompts):
    async def handler(message, response_type, params, context):
        prompts.append(message)
        return {"approve": True}
    return handler


def answering(prompts, action):
    async def handler(message, response_type, params, context):
        prompts.append(message)
        return ElicitResult(action=action)
    return handler


def test_the_person_approves_and_the_payment_runs_without_the_model_confirming(net):
    prompts = []
    call("mpesa_b2c", dict(PAY), approving(prompts))          # note: no confirm_send from the model
    assert len(prompts) == 1 and net, "the person was asked once and the payment then reached the network"
    p = prompts[0]
    assert "0712345678" in p and "254712345678" in p and "KES 500" in p and "mpesa_b2c" in p and "Approve only if you asked for exactly this payment" in p


@pytest.mark.parametrize("action", ["decline", "cancel"])
def test_a_person_who_declines_or_cancels_stops_the_payment_even_if_the_model_says_confirm(net, action):
    prompts = []
    r = call("mpesa_b2c", dict(PAY, confirm_send=True), answering(prompts, action))
    assert prompts and not net, "the network must never be reached"
    assert "declined" in text(r)
    rep = fn("mpesa_session_report")()
    assert rep["spent_kes"] == 0 and rep["blocked_count"] == 1 and rep["recent"][-1]["outcome"] == "BLOCKED_DECLINED_BY_HUMAN"


def test_a_client_that_cannot_answer_falls_back_to_the_confirm_parameter_in_auto_mode(net):
    assert "Confirmation required" in text(call("mpesa_b2c", dict(PAY)))
    assert not net
    call("mpesa_b2c", dict(PAY, confirm_send=True))
    assert net


def test_strict_mode_refuses_when_the_client_cannot_show_a_prompt_even_with_the_parameter(net, monkeypatch):
    monkeypatch.setenv("MPESA_CONFIRM_MODE", "elicit")
    assert "cannot show a confirmation prompt" in text(call("mpesa_b2c", dict(PAY, confirm_send=True)))
    assert not net
    call("mpesa_b2c", dict(PAY), approving([]))
    assert net


def test_param_mode_is_the_old_behaviour_and_never_prompts(net, monkeypatch):
    monkeypatch.setenv("MPESA_CONFIRM_MODE", "param")
    prompts = []
    call("mpesa_b2c", dict(PAY, confirm_send=True), approving(prompts))
    assert net and not prompts


@pytest.mark.parametrize("case", ["cap", "allowlist", "budget"])
def test_a_payment_that_would_be_refused_anyway_does_not_ask_the_person(net, monkeypatch, case):
    prompts = []
    args = dict(PAY)
    if case == "cap":
        args["amount"] = server.DEFAULT_LIVE_CAP_KES + 1
    elif case == "allowlist":
        monkeypatch.setenv("MPESA_ALLOWED_RECIPIENTS", "0799999999")
    else:
        monkeypatch.setenv("MPESA_SESSION_BUDGET_KES", "100")
    r = call("mpesa_b2c", args, approving(prompts))
    assert not prompts and not net and r.is_error is False
    assert {"cap": "cap of KES", "allowlist": "allowlist", "budget": "Session budget"}[case] in text(r)


def test_nobody_is_prompted_in_the_sandbox_when_confirmation_is_switched_off_or_for_non_money_tools(net, monkeypatch):
    prompts = []
    monkeypatch.setenv("MPESA_REQUIRE_CONFIRMATION", "false")
    call("mpesa_b2c", dict(PAY), approving(prompts))
    monkeypatch.delenv("MPESA_REQUIRE_CONFIRMATION")
    monkeypatch.setenv("MPESA_SANDBOX", "true")
    call("mpesa_b2c", dict(PAY), approving(prompts))
    monkeypatch.setenv("MPESA_SANDBOX", "false")
    assert call("mpesa_session_report", {}, approving(prompts)).is_error is False
    assert not prompts


def test_the_guarded_set_is_exactly_the_set_of_tools_that_call_the_guard():
    """A new money tool that calls the guard but is missing here would skip the person's confirmation."""
    called = set(re.findall(r'_guard\("([a-z0-9_]+)"', SRC.read_text(encoding="utf-8")))
    assert called == set(confirm.GUARDED), called ^ set(confirm.GUARDED)
    for tool, param in confirm.GUARDED.items():
        if param:
            assert param in inspect.signature(fn(tool)).parameters, (tool, param)


def test_a_reversal_prompt_shows_the_transaction_being_reversed():
    p = confirm.describe("mpesa_reversal", {"transaction_id": "ABC123", "amount": 500})
    assert "Transaction id: ABC123" in p and "KES 500" in p and "Pay to" not in p


def test_an_approval_is_bound_to_the_exact_call_single_use_and_short_lived():
    args = {"phone": "0712345678", "amount": 500}
    s = confirm.make_state("mpesa_b2c", args)
    assert confirm.state_is_valid_and_consume(s, "mpesa_b2c", {**args, "confirm_send": True}), "the confirm_send flag does not change which call it is"
    assert not confirm.state_is_valid_and_consume(s, "mpesa_b2c", args), "single use: a replay is refused"
    t = confirm.make_state("mpesa_b2c", args)
    assert not confirm.state_is_valid_and_consume(t, "mpesa_b2c", {**args, "amount": 50_000}), "a different amount is a different call"
    assert not confirm.state_is_valid_and_consume(t, "mpesa_b2c", {**args, "phone": "0799999999"}), "a different recipient is a different call"
    assert not confirm.state_is_valid_and_consume(t, "airtime_send", args), "a different tool is a different call"
    u = confirm.make_state("mpesa_b2c", args, now=time.time() - confirm.APPROVAL_TTL_SECONDS - 5)
    assert not confirm.state_is_valid_and_consume(u, "mpesa_b2c", args), "an old approval has expired"
    for junk in (None, "", "a.b", "x.y.z", "abc.def.1"):
        assert not confirm.state_is_valid_and_consume(junk, "mpesa_b2c", args)


# ---- the older protocol era, where Context.elicit asks inside the same call: a faithful fake of the context the middleware sees
class _Msg:
    def __init__(self, name, arguments):
        self.name, self.arguments = name, arguments

    def model_copy(self, update):
        return _Msg(self.name, update["arguments"])


class _Session:
    def check_client_capability(self, cap):
        return True


class _Ctx:
    def __init__(self, answer):
        self.answer, self.session, self.prompts = answer, _Session(), []

    def _is_modern_protocol(self):
        return False

    async def elicit(self, message, response_type):
        self.prompts.append(message)
        return self.answer


class _MCtx:
    def __init__(self, message, fastmcp_context):
        self.message, self.fastmcp_context = message, fastmcp_context

    def copy(self, message):
        return _MCtx(message, self.fastmcp_context)


def _legacy(answer, live_env_args=None):
    ctx = _Ctx(answer)
    seen = []

    async def call_next(c):
        seen.append(dict(c.message.arguments))
        return "RAN"
    out = asyncio.run(confirm.HumanConfirmation().on_call_tool(_MCtx(_Msg("mpesa_b2c", dict(PAY)), ctx), call_next))
    return out, seen, ctx


def test_older_era_accept_sets_confirm_send_for_the_tool_and_asks_once(live):
    out, seen, ctx = _legacy(AcceptedElicitation(data=True))
    assert out == "RAN" and seen == [{**PAY, "confirm_send": True}] and len(ctx.prompts) == 1


@pytest.mark.parametrize("answer", [DeclinedElicitation(), CancelledElicitation(), AcceptedElicitation(data=False)])
def test_older_era_anything_but_a_yes_stops_the_payment(live, answer):
    out, seen, ctx = _legacy(answer)
    assert out != "RAN" and not seen


# ---- the modern era driven directly: the middleware must itself enforce binding, single use and the person's answer
class _Reply:
    def __init__(self, action="accept", approve=True):
        self.action, self.content = action, {"approve": approve}


class _ModernCtx(_Ctx):
    def __init__(self, input_responses=None, request_state=None):
        super().__init__(None)
        self.input_responses, self.request_state = input_responses, request_state

    def _is_modern_protocol(self):
        return True


def _modern(args, reply, state):
    from fastmcp.tools.base import InputRequiredToolResult
    ctx = _ModernCtx({confirm.CONFIRM_KEY: reply} if reply is not None else None, state)
    seen = []

    async def call_next(c):
        seen.append(dict(c.message.arguments))
        return "RAN"
    out = asyncio.run(confirm.HumanConfirmation().on_call_tool(_MCtx(_Msg("mpesa_b2c", dict(args)), ctx), call_next))
    return out, seen, isinstance(out, InputRequiredToolResult)


def test_modern_era_the_first_leg_asks_and_carries_a_state_bound_to_this_exact_call(live):
    out, seen, asked = _modern(PAY, None, None)
    assert asked and not seen
    state = out.input_required.request_state
    assert state.split(".")[0] == confirm._digest("mpesa_b2c", PAY)
    assert "0712345678" in out.input_required.input_requests[confirm.CONFIRM_KEY].params.message


def test_modern_era_a_valid_approval_runs_the_payment_with_confirm_send_set_by_the_server(live):
    state = confirm.make_state("mpesa_b2c", PAY)
    out, seen, asked = _modern(PAY, _Reply(), state)
    assert out == "RAN" and seen == [{**PAY, "confirm_send": True}] and not asked


def test_modern_era_an_approval_for_one_amount_cannot_be_reused_for_another(live):
    state = confirm.make_state("mpesa_b2c", PAY)
    out, seen, asked = _modern({**PAY, "amount": 5_000}, _Reply(), state)
    assert asked and not seen, "a tampered call must be asked about again, never run"


def test_modern_era_an_approval_cannot_be_replayed_for_a_second_payment(live):
    state = confirm.make_state("mpesa_b2c", PAY)
    assert _modern(PAY, _Reply(), state)[0] == "RAN"
    out, seen, asked = _modern(PAY, _Reply(), state)
    assert asked and not seen


@pytest.mark.parametrize("reply", [_Reply("decline"), _Reply("cancel"), _Reply("accept", approve=False)])
def test_modern_era_anything_but_a_yes_stops_the_payment(live, reply):
    state = confirm.make_state("mpesa_b2c", PAY)
    out, seen, asked = _modern(PAY, reply, state)
    assert not seen and not asked and out != "RAN"
