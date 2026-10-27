"""The session budget is process-wide state: reset it around every test so no test inherits another's spending."""
import pytest
from helpers import Reached

from mpesa_mcp import server


@pytest.fixture(autouse=True)
def _fresh_session_budget(monkeypatch):
    monkeypatch.delenv("MPESA_SESSION_BUDGET_KES", raising=False)
    server._reset_session_spend()
    yield
    server._reset_session_spend()


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
