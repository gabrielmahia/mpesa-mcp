"""The session budget is process-wide state: reset it around every test so no test inherits another's spending."""
import pytest

from mpesa_mcp import server


@pytest.fixture(autouse=True)
def _fresh_session_budget(monkeypatch):
    monkeypatch.delenv("MPESA_SESSION_BUDGET_KES", raising=False)
    server._reset_session_spend()
    yield
    server._reset_session_spend()
