"""The audit trail must say how a money call ended, and a missing credential must say which one is missing."""
import ast
import asyncio
import logging
import pathlib
import re

import pytest
import requests
from fastmcp import Client

from mpesa_mcp import server as srv

SERVER_SRC = pathlib.Path(srv.__file__).read_text(encoding="utf-8")


def outcomes(caplog, tool):
    return [m.group(1) for r in caplog.records if (m := re.search(rf"TOOL={tool} .*OUTCOME=(\S+)", r.getMessage()))]


class _Reply:
    def __init__(self, code="0", http_error=None):
        self._code, self._err = code, http_error

    def raise_for_status(self):
        if self._err:
            raise self._err

    def json(self):
        return {"ResponseCode": self._code, "ConversationID": "AG_1", "OriginatorConversationID": "O_1", "ResponseDescription": "x"}


@pytest.fixture
def sandbox(monkeypatch):
    """Sandbox mode with fake credentials and every network call replaced, so nothing real can be reached."""
    for k in ("MPESA_INITIATOR_NAME", "MPESA_SECURITY_CREDENTIAL", "MPESA_SHORTCODE", "MPESA_PASSKEY"):
        monkeypatch.setenv(k, "fake")
    monkeypatch.setenv("MPESA_SANDBOX", "true")
    monkeypatch.setattr(srv, "_get_mpesa_token", lambda: "token")
    monkeypatch.setattr(srv, "_result_url", lambda: "https://example.invalid/result")
    monkeypatch.setattr(srv, "_timeout_url", lambda: "https://example.invalid/timeout")
    return monkeypatch


def b2c():
    return srv.mpesa_b2c(phone="254700000000", amount=10, confirm_send=False)


def test_an_accepted_payment_is_recorded_as_accepted(sandbox, caplog):
    sandbox.setattr(srv.requests, "post", lambda *a, **k: _Reply("0"))
    with caplog.at_level(logging.INFO):
        assert b2c()["accepted"] is True
    assert outcomes(caplog, "mpesa_b2c") == ["INITIATED", "ACCEPTED"]


def test_a_rejected_payment_is_recorded_with_the_response_code(sandbox, caplog):
    sandbox.setattr(srv.requests, "post", lambda *a, **k: _Reply("2001"))
    with caplog.at_level(logging.INFO):
        assert b2c()["accepted"] is False
    assert outcomes(caplog, "mpesa_b2c") == ["INITIATED", "REJECTED:2001"]


def test_an_http_failure_is_recorded_and_the_exception_still_propagates(sandbox, caplog):
    sandbox.setattr(srv.requests, "post", lambda *a, **k: _Reply(http_error=requests.HTTPError("500")))
    with caplog.at_level(logging.INFO), pytest.raises(requests.HTTPError):
        b2c()
    assert outcomes(caplog, "mpesa_b2c") == ["INITIATED", "FAILED:HTTPError"]


def test_a_missing_credential_names_the_variable_and_the_audit_shows_it_failed(sandbox, caplog):
    sandbox.delenv("MPESA_SHORTCODE")
    sandbox.setattr(srv.requests, "post", lambda *a, **k: _Reply("0"))
    with caplog.at_level(logging.INFO), pytest.raises(srv.ConfigError, match="MPESA_SHORTCODE is not set"):
        b2c()
    assert outcomes(caplog, "mpesa_b2c") == ["INITIATED", "FAILED:ConfigError"], "it used to stop at INITIATED forever"


def test_through_the_mcp_client_the_message_is_readable_not_a_bare_key_name(sandbox):
    sandbox.delenv("MPESA_SHORTCODE")

    async def go():
        async with Client(srv.mcp) as c:
            r = await c.call_tool("mpesa_b2c", {"phone": "254700000000", "amount": 10}, raise_on_error=False)
            return " ".join(getattr(b, "text", "") for b in r.content)

    assert "MPESA_SHORTCODE is not set" in asyncio.run(go())


def test_a_live_mode_refusal_is_audited_once_as_blocked_and_never_reaches_the_network(sandbox, caplog):
    sandbox.setenv("MPESA_SANDBOX", "false")
    sandbox.setattr(srv.requests, "post", lambda *a, **k: pytest.fail("the network must not be reached when the guard refuses"))
    with caplog.at_level(logging.INFO):
        result = srv.mpesa_b2c(phone="254700000000", amount=10, confirm_send=False)
    assert result["success"] is False and "Confirmation required" in result["error"]
    assert outcomes(caplog, "mpesa_b2c") == ["BLOCKED_NO_CONFIRMATION"]


def test_wrapping_does_not_change_the_tool_schema_clients_see():
    async def go():
        async with Client(srv.mcp) as c:
            return {t.name: t for t in await c.list_tools()}

    tools = asyncio.run(go())
    schema = tools["mpesa_b2c"].inputSchema
    assert {"phone", "amount", "confirm_send"} <= set(schema["properties"]) and set(schema["required"]) == {"phone", "amount"}
    assert len(tools) == 23


def test_every_tool_that_logs_initiated_is_decorated_so_a_new_money_tool_cannot_skip_the_terminal_line():
    tree = ast.parse(SERVER_SRC)
    missing = []
    for fn in (n for n in tree.body if isinstance(n, ast.FunctionDef)):
        logs_initiated = any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "_audit" and c.args and ast.unparse(c.args[-1]) == "'INITIATED'" for c in ast.walk(fn))
        if logs_initiated and not any("_terminal_audit" in ast.unparse(d) for d in fn.decorator_list):
            missing.append(fn.name)
    assert missing == []


def test_there_are_no_bare_environment_reads_by_literal_name_left():
    """Every credential read goes through _env, which names the missing variable; the helper itself reads by variable, not by literal."""
    reads = [i for i, line in enumerate(SERVER_SRC.split("\n"), 1) if 'os.environ["' in line or "os.environ['" in line]
    assert reads == [], f"bare reads at lines {reads}"
