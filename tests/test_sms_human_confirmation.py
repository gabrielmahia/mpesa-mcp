"""sms_send messages real people (cost, spam, phishing in the operator's name), so in live mode the person approves it through the client, exactly like a payment.
The model-supplied confirm_send alone is not an independent check (found 2026-11-10 against the installed 0.7.0: a model could message 50 people per call, repeatedly)."""
import asyncio
import types

import pytest
from fastmcp import Client
from fastmcp.client.elicitation import ElicitResult

from mpesa_mcp import confirm, server

MSG = {"message": "Your repayment of KES 1,200 is due on Friday.", "recipients": ["+254712345678", "+254722000111"]}


class _FakeSMS:
    sent: list = []

    @classmethod
    def send(cls, **kw):
        cls.sent.append(kw)
        return {"SMSMessageData": {"Message": "ok", "Recipients": [{"number": n, "status": "Success", "cost": "KES 0.8", "messageId": "x"} for n in kw["recipients"]]}}


@pytest.fixture
def sms(live, monkeypatch):
    _FakeSMS.sent = []
    monkeypatch.setattr(server, "_at_init", lambda: None)
    monkeypatch.setattr(server, "africastalking", types.SimpleNamespace(SMS=_FakeSMS), raising=False)
    monkeypatch.delenv("MPESA_MAX_SMS_RECIPIENTS", raising=False)
    monkeypatch.delenv("MPESA_CONFIRM_MODE", raising=False)
    return _FakeSMS


def call(args, handler=None):
    async def go():
        client = Client(server.mcp, elicitation_handler=handler) if handler else Client(server.mcp)
        async with client as c:
            r = await c.call_tool("sms_send", args, raise_on_error=False)
            return " ".join(getattr(b, "text", "") for b in r.content) + " " + str(getattr(r, "structured_content", None))
    return asyncio.run(go())


def approving(prompts):
    async def handler(message, response_type, params, context):
        prompts.append(message)
        return {"approve": True}
    return handler


def declining(prompts):
    async def handler(message, response_type, params, context):
        prompts.append(message)
        return ElicitResult(action="decline")
    return handler


def test_by_default_a_client_that_cannot_ask_cannot_send_even_with_confirm_send(sms):
    out = call(dict(MSG, confirm_send=True))
    assert "confirm each SMS" in out and not sms.sent


def test_the_person_approves_and_the_sms_is_sent_without_the_model_confirming(sms):
    prompts = []
    out = call(dict(MSG), approving(prompts))               # no confirm_send from the model
    assert len(prompts) == 1 and len(sms.sent) == 1 and sms.sent[0]["recipients"] == MSG["recipients"] and '"sent":2' in out.replace(" ", "")
    p = prompts[0]
    assert "Your repayment of KES 1,200 is due on Friday." in p and "+254712345678" in p and "+254722000111" in p and "2 recipient(s)" in p and "exactly this message to exactly these people" in p


def test_the_person_declines_and_nothing_is_sent(sms):
    prompts = []
    out = call(dict(MSG, confirm_send=True), declining(prompts))
    assert len(prompts) == 1 and not sms.sent and "declined this SMS" in out


def test_over_the_cap_is_refused_without_asking_the_person(sms, monkeypatch):
    monkeypatch.setenv("MPESA_MAX_SMS_RECIPIENTS", "2")
    prompts = []
    out = call({"message": "hi", "recipients": ["+254700000001", "+254700000002", "+254700000003"]}, approving(prompts))
    assert not prompts and not sms.sent and "per-call cap" in out


def test_an_empty_recipient_list_is_refused_without_asking_the_person(sms):
    prompts = []
    out = call({"message": "hi", "recipients": []}, approving(prompts))
    assert not prompts and not sms.sent and "non-empty" in out


def test_the_approval_is_bound_to_the_exact_message_and_recipients():
    state = confirm.make_state("sms_send", MSG)
    other = dict(MSG, message="Send KES 5,000 to this number to keep your account.")
    assert confirm.state_is_valid_and_consume(state, "sms_send", other) is False        # a different message needs a new approval
    assert confirm.state_is_valid_and_consume(state, "sms_send", dict(MSG, recipients=MSG["recipients"] + ["+254799999999"])) is False
    assert confirm.state_is_valid_and_consume(state, "sms_send", MSG) is True and confirm.state_is_valid_and_consume(state, "sms_send", MSG) is False   # once only


def test_the_prompt_shows_ten_recipients_then_the_count_and_truncates_a_long_message():
    many = [f"+2547000000{i:02d}" for i in range(25)]
    p = confirm.describe("sms_send", {"message": "x" * 700, "recipients": many, "sender_id": "ACME"})
    assert "To 25 recipient(s)" in p and "+254700000009" in p and "+254700000010" not in p and "and 15 more" in p and "[...]" in p and "Sender ID: ACME" in p


def test_the_explicit_auto_opt_in_still_falls_back_to_the_parameter(sms, monkeypatch):
    monkeypatch.setenv("MPESA_CONFIRM_MODE", "auto")
    assert len(sms.sent) == 0
    call(dict(MSG, confirm_send=True))
    assert len(sms.sent) == 1


def test_the_sandbox_is_never_prompted(sms, monkeypatch):
    monkeypatch.setenv("MPESA_SANDBOX", "true")
    prompts = []
    call(dict(MSG), approving(prompts))
    assert not prompts and len(sms.sent) == 1
