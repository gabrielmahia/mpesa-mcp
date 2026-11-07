"""Both audit lines for one call must hash the phone identically, however the caller typed it."""
import logging
import re

from helpers import fn

from mpesa_mcp import server


class _Resp:
    def raise_for_status(self):
        return None

    def json(self):
        return {"ResponseHeader": {"responseRefID": "r", "responseCode": "200", "responseDescription": "Request accepted for processing"}}


def test_initiated_and_terminal_lines_hash_the_phone_the_same(monkeypatch, caplog):
    monkeypatch.setenv("MPESA_SHORTCODE", "174379")
    monkeypatch.setenv("MPESA_CALLBACK_URL", "https://example.com/cb")
    monkeypatch.setattr(server, "_get_mpesa_token", lambda: "tok")
    monkeypatch.setattr(server.requests, "post", lambda *a, **k: _Resp())
    with caplog.at_level(logging.INFO, logger="mpesa_mcp"):
        fn("mpesa_ratiba_create")(phone="0712345678", amount=10, standing_order_name="S", start_date="2030-01-01", end_date="2030-03-01", account_ref="A")
    hashes = [re.search(r"'phone': '([0-9a-f]{8})", r.getMessage()).group(1) for r in caplog.records if "TOOL=mpesa_ratiba_create" in r.getMessage()]
    assert len(hashes) == 2 and hashes[0] == hashes[1]
    assert server._audit_hash("0712345678") == server._audit_hash("+254712345678") == server._audit_hash("254712345678")
