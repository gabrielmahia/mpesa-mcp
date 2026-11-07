"""mpesa_ratiba_create: payload mapping, validation, schedule arithmetic and honesty, with Daraja mocked."""
import datetime

import pytest
from helpers import fn

from mpesa_mcp import server

RATIBA = fn("mpesa_ratiba_create")


class _Resp:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self.data


@pytest.fixture
def daraja(monkeypatch):
    sent = {}
    monkeypatch.setenv("MPESA_SHORTCODE", "174379")
    monkeypatch.setenv("MPESA_CALLBACK_URL", "https://example.com/cb")
    monkeypatch.setattr(server, "_get_mpesa_token", lambda: "tok")
    def post(url, json=None, headers=None, timeout=None):
        sent.update(url=url, body=json)
        return _Resp({"ResponseHeader": {"responseRefID": "ref-1", "responseCode": "200", "responseDescription": "Request accepted for processing"}})
    monkeypatch.setattr(server.requests, "post", post)
    return sent


def test_payload_matches_the_daraja_specification(daraja):
    r = RATIBA(phone="0712345678", amount=500, standing_order_name="Loan 42", start_date="2030-01-15", end_date="20300615", frequency="monthly", account_ref="LN42", description="Loan repay")
    b = daraja["body"]
    assert daraja["url"].endswith("/standingorder/v1/createStandingOrderExternal")
    assert b == {"StandingOrderName": "Loan 42", "StartDate": "20300115", "EndDate": "20300615", "BusinessShortCode": "174379", "TransactionType": "Standing Order Customer Pay Bill",
                 "ReceiverPartyIdentifierType": "4", "Amount": "500", "PartyA": "254712345678", "CallBackURL": "https://example.com/cb", "AccountReference": "LN42",
                 "TransactionDesc": "Loan repay", "Frequency": "4"}
    assert r["success"] and r["response_ref_id"] == "ref-1" and r["schedule"]["payments"] == 6 and r["schedule"]["total_commitment_kes"] == 3000


def test_till_uses_safaricoms_buy_goods_type_and_receiver_code(daraja):
    RATIBA(phone="254712345678", amount=100, standing_order_name="Sub", start_date="2030-01-01", end_date="2030-01-29", frequency="weekly", account_ref="S1", receiver_type="till")
    assert daraja["body"]["TransactionType"] == "Standing Order Customer Pay Marchant" and daraja["body"]["ReceiverPartyIdentifierType"] == "2" and daraja["body"]["Frequency"] == "3"


@pytest.mark.parametrize("freq,start,end,count", [("daily", "2030-01-01", "2030-01-10", 10), ("weekly", "2030-01-01", "2030-01-29", 5), ("monthly", "2030-01-31", "2030-04-30", 4),
                                                  ("quarterly", "2030-01-01", "2030-12-31", 4), ("half_year", "2030-01-01", "2031-01-01", 3), ("yearly", "2030-02-28", "2032-02-28", 3), ("one_off", "2030-01-01", "2030-12-31", 1)])
def test_schedule_counts_payments_from_the_dates(daraja, freq, start, end, count):
    r = RATIBA(phone="254712345678", amount=10, standing_order_name="S", start_date=start, end_date=end, frequency=freq, account_ref="A")
    assert r["schedule"]["payments"] == count and r["schedule"]["total_commitment_kes"] == 10 * count


def test_bi_monthly_gives_no_guessed_number(daraja):
    r = RATIBA(phone="254712345678", amount=10, standing_order_name="S", start_date="2030-01-01", end_date="2030-12-31", frequency="bi_monthly", account_ref="A")
    assert r["schedule"]["payments"] is None and r["schedule"]["total_commitment_kes"] is None and "Bi-Monthly" in r["schedule"]["note"] and daraja["body"]["Frequency"] == "5"


@pytest.mark.parametrize("kw,msg", [({"frequency": "fortnightly"}, "frequency"), ({"receiver_type": "bank"}, "receiver_type"), ({"amount": 0}, "amount"), ({"amount": 150001}, "amount"),
                                    ({"account_ref": "X" * 13}, "account_ref"), ({"standing_order_name": ""}, "standing_order_name"),
                                    ({"start_date": "2020-01-01"}, "past"), ({"end_date": "2029-12-31"}, "before"), ({"start_date": "15/01/2030"}, "YYYY")])
def test_invalid_input_is_refused_before_any_request(monkeypatch, kw, msg):
    def never(*a, **k):
        raise AssertionError("no request should be made")
    monkeypatch.setattr(server.requests, "post", never)
    args = {"phone": "254712345678", "amount": 100, "standing_order_name": "S", "start_date": "2030-01-01", "end_date": "2030-06-01", "frequency": "monthly", "account_ref": "A", **kw}
    r = RATIBA(**args)
    assert r["success"] is False and msg in r["error"]


def test_month_end_dates_clamp_instead_of_skipping():
    assert server._add_months(datetime.date(2030, 1, 31), 1) == datetime.date(2030, 2, 28)


def test_safaricom_codes_and_long_descriptions_still_work_as_before(daraja):
    r = RATIBA(phone="254712345678", amount=10, standing_order_name="S", start_date="2030-01-01", end_date="2030-03-01", frequency="4", account_ref="A", description="Standing order via mpesa-mcp")
    assert daraja["body"]["Frequency"] == "4" and daraja["body"]["TransactionDesc"] == "Standing orde" and r["schedule"]["frequency"] == "monthly" and r["schedule"]["payments"] == 3


def test_the_old_wrong_endpoint_and_stk_password_are_gone(daraja):
    RATIBA(phone="254712345678", amount=10, standing_order_name="S", start_date="2030-01-01", end_date="2030-03-01", account_ref="A")
    assert "/v1/ratiba/create" not in daraja["url"] and "Password" not in daraja["body"] and "Timestamp" not in daraja["body"] and "PartyB" not in daraja["body"]
