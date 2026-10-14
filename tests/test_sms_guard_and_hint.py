import types

import pytest

from mpesa_mcp import server

_fn = lambda name: (getattr(server, name).fn if hasattr(getattr(server, name), "fn") else getattr(server, name))  # noqa: E731


class _FakeSMS:
    sent: list = []

    @classmethod
    def send(cls, **kw):
        cls.sent.append(kw)
        return {"SMSMessageData": {"Message": "ok", "Recipients": [{"number": n, "status": "Success", "cost": "KES 0.8", "messageId": "x"} for n in kw["recipients"]]}}


@pytest.fixture
def sms(monkeypatch):
    _FakeSMS.sent = []
    monkeypatch.setattr(server, "_at_init", lambda: None)
    monkeypatch.setattr(server, "africastalking", types.SimpleNamespace(SMS=_FakeSMS), raising=False)
    monkeypatch.delenv("MPESA_MAX_SMS_RECIPIENTS", raising=False)
    monkeypatch.delenv("MPESA_REQUIRE_CONFIRMATION", raising=False)
    return _FakeSMS


def test_live_mode_refuses_an_unconfirmed_sms_and_sends_nothing(sms, monkeypatch):
    monkeypatch.setenv("MPESA_SANDBOX", "false")
    r = _fn("sms_send")("hello", ["+254700000001"])
    assert r["success"] is False and "Confirmation required" in r["error"] and sms.sent == []


def test_live_mode_sends_after_confirmation_and_blocks_over_the_cap(sms, monkeypatch):
    monkeypatch.setenv("MPESA_SANDBOX", "false")
    assert _fn("sms_send")("hello", ["+254700000001"], "", True)["sent"] == 1
    r = _fn("sms_send")("hello", [f"+2547000{i:05d}" for i in range(51)], "", True)
    assert r["success"] is False and "cap of 50" in r["error"] and len(sms.sent) == 1
    monkeypatch.setenv("MPESA_MAX_SMS_RECIPIENTS", "0")
    assert _fn("sms_send")("hello", [f"+2547000{i:05d}" for i in range(51)], "", True)["sent"] == 51


def test_an_empty_recipient_list_is_refused_in_live_mode(sms, monkeypatch):
    monkeypatch.setenv("MPESA_SANDBOX", "false")
    assert _fn("sms_send")("hello", [], "", True)["success"] is False


def test_the_sandbox_is_never_restricted(sms, monkeypatch):
    monkeypatch.setenv("MPESA_SANDBOX", "true")
    assert _fn("sms_send")("hello", ["+254700000001"])["sent"] == 1


def test_the_model_hint_carries_no_unsourced_benchmark_or_expired_price():
    text = str(_fn("get_model_hint")())
    assert "Terminal-Bench" not in text and "$2/$10" not in text and "claude-opus-4-8" not in text and _fn("get_model_hint")()["recommended_model"] is None
