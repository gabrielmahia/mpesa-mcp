"""
mpesa-mcp — MCP server for East African fintech APIs

Tools:
  M-Pesa (Safaricom Daraja):
    mpesa_stk_push          — trigger payment prompt on customer's phone
    mpesa_stk_query         — check STK push status
    mpesa_transaction_status — query any M-Pesa transaction

  Africa's Talking:
    sms_send                — send SMS to one or many recipients
    airtime_send            — send airtime top-up

Environment variables required:
  MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET, MPESA_SHORTCODE,
  MPESA_PASSKEY, MPESA_CALLBACK_URL
  AT_USERNAME, AT_API_KEY
  MPESA_SANDBOX=true  (set false for production)
"""

import base64
import datetime
import os
import time
from typing import Annotated

import africastalking
import requests
from fastmcp import FastMCP

mcp = FastMCP(
    name="mpesa-mcp",
    instructions=(
        "Tools for M-Pesa (Safaricom Daraja) and Africa's Talking APIs. "
        "Covers Kenya mobile payments (STK Push, C2B, transaction status) "
        "and SMS/airtime delivery across African telecom networks. "
        "Set MPESA_SANDBOX=true for testing — no real money moves."
    ),
)

# ── Auth helpers ──────────────────────────────────────────────────────────────

_token_cache: dict = {"token": None, "expires_at": 0.0}


def _get_mpesa_token() -> str:
    if time.time() < _token_cache["expires_at"] - 30:
        return _token_cache["token"]  # type: ignore[return-value]

    sandbox = os.environ.get("MPESA_SANDBOX", "true").lower() == "true"
    base = "https://sandbox.safaricom.co.ke" if sandbox else "https://api.safaricom.co.ke"

    key    = os.environ["MPESA_CONSUMER_KEY"]
    secret = os.environ["MPESA_CONSUMER_SECRET"]
    creds  = base64.b64encode(f"{key}:{secret}".encode()).decode()

    resp = requests.get(
        f"{base}/oauth/v1/generate?grant_type=client_credentials",
        headers={"Authorization": f"Basic {creds}"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"]      = data["access_token"]
    _token_cache["expires_at"] = time.time() + int(data["expires_in"])
    return _token_cache["token"]  # type: ignore[return-value]


def _mpesa_base() -> str:
    sandbox = os.environ.get("MPESA_SANDBOX", "true").lower() == "true"
    return "https://sandbox.safaricom.co.ke" if sandbox else "https://api.safaricom.co.ke"


def _normalize_phone(phone: str) -> str:
    """Normalize to 12-digit Kenyan format: 254XXXXXXXXX."""
    phone = phone.strip().lstrip("+")
    if phone.startswith("0"):
        phone = "254" + phone[1:]
    elif not phone.startswith("254"):
        phone = "254" + phone
    return phone


def _at_sms():
    africastalking.initialize(
        username=os.environ["AT_USERNAME"],
        api_key=os.environ["AT_API_KEY"],
    )
    return africastalking.SMS


def _at_airtime():
    africastalking.initialize(
        username=os.environ["AT_USERNAME"],
        api_key=os.environ["AT_API_KEY"],
    )
    return africastalking.Airtime


# ── M-Pesa tools ─────────────────────────────────────────────────────────────

@mcp.tool(annotations={
    'title': 'M-Pesa STK Push',
    'readOnlyHint': False,
    'destructiveHint': True,
    'idempotentHint': False,
    'openWorldHint': True,
})
def mpesa_stk_push(
    phone: Annotated[str, "Customer phone number (any Kenyan format: +254..., 07..., 254...)"],
    amount: Annotated[int, "Amount in KES (whole number, minimum 1)"],
    account_ref: Annotated[str, "Account reference shown to customer on their phone (max 12 chars)"],
    description: Annotated[str, "Transaction description (max 13 chars)"] = "Payment",
) -> dict:
    """
    Trigger an M-Pesa STK Push — sends a payment prompt to the customer's phone.
    The customer enters their M-Pesa PIN to complete payment.
    Returns a CheckoutRequestID to track the transaction with mpesa_stk_query.
    Async: use mpesa_stk_query after 10-30 seconds to check completion.
    """
    shortcode = os.environ["MPESA_SHORTCODE"]
    passkey   = os.environ["MPESA_PASSKEY"]
    callback  = os.environ["MPESA_CALLBACK_URL"]
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    password  = base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode()
    phone     = _normalize_phone(phone)

    payload = {
        "BusinessShortCode": shortcode,
        "Password":          password,
        "Timestamp":         timestamp,
        "TransactionType":   "CustomerPayBillOnline",
        "Amount":            amount,
        "PartyA":            phone,
        "PartyB":            shortcode,
        "PhoneNumber":       phone,
        "CallBackURL":       callback,
        "AccountReference":  account_ref[:12],
        "TransactionDesc":   description[:13],
    }

    token = _get_mpesa_token()
    resp  = requests.post(
        f"{_mpesa_base()}/mpesa/stkpush/v1/processrequest",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    return {
        "success":            data.get("ResponseCode") == "0",
        "checkout_request_id": data.get("CheckoutRequestID"),
        "merchant_request_id": data.get("MerchantRequestID"),
        "response_code":       data.get("ResponseCode"),
        "message":             data.get("CustomerMessage", data.get("ResponseDescription")),
        "sandbox":             os.environ.get("MPESA_SANDBOX", "true").lower() == "true",
    }


@mcp.tool(annotations={
    'title': 'M-Pesa STK Query',
    'readOnlyHint': True,
    'destructiveHint': False,
    'idempotentHint': True,
    'openWorldHint': True,
})
def mpesa_stk_query(
    checkout_request_id: Annotated[str, "CheckoutRequestID from mpesa_stk_push response"],
) -> dict:
    """
    Check the status of an STK Push request.
    Poll this 10-30 seconds after calling mpesa_stk_push.
    ResultCode 0 = success, 1032 = cancelled by user, 1037 = timed out.
    """
    shortcode = os.environ["MPESA_SHORTCODE"]
    passkey   = os.environ["MPESA_PASSKEY"]
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    password  = base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode()

    payload = {
        "BusinessShortCode":  shortcode,
        "Password":           password,
        "Timestamp":          timestamp,
        "CheckoutRequestID":  checkout_request_id,
    }

    token = _get_mpesa_token()
    resp  = requests.post(
        f"{_mpesa_base()}/mpesa/stkpushquery/v1/query",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    result_code = int(data.get("ResultCode", -1))
    status_map  = {
        0:    "SUCCESS",
        1:    "INSUFFICIENT_FUNDS",
        1001: "LOCKED — retry in 30s",
        1019: "EXPIRED — re-initiate",
        1032: "CANCELLED_BY_USER",
        1037: "TIMEOUT",
        2001: "WRONG_PIN",
    }

    return {
        "success":      result_code == 0,
        "result_code":  result_code,
        "status":       status_map.get(result_code, f"UNKNOWN ({result_code})"),
        "description":  data.get("ResultDesc"),
    }


@mcp.tool(annotations={
    'title': 'M-Pesa Transaction Status',
    'readOnlyHint': True,
    'destructiveHint': False,
    'idempotentHint': True,
    'openWorldHint': True,
})
def mpesa_transaction_status(
    transaction_id: Annotated[str, "M-Pesa receipt number e.g. QKL8XXXXXX"],
) -> dict:
    """
    Query the status of any M-Pesa transaction by receipt number.
    Requires MPESA_INITIATOR_NAME and MPESA_SECURITY_CREDENTIAL env vars.
    """
    payload = {
        "Initiator":           os.environ["MPESA_INITIATOR_NAME"],
        "SecurityCredential":  os.environ["MPESA_SECURITY_CREDENTIAL"],
        "CommandID":           "TransactionStatusQuery",
        "TransactionID":       transaction_id,
        "PartyA":              os.environ["MPESA_SHORTCODE"],
        "IdentifierType":      "4",
        "ResultURL":           os.environ.get("MPESA_RESULT_URL", os.environ["MPESA_CALLBACK_URL"]),
        "QueueTimeOutURL":     os.environ.get("MPESA_TIMEOUT_URL", os.environ["MPESA_CALLBACK_URL"]),
        "Remarks":             "Status query via mpesa-mcp",
        "Occasion":            "",
    }

    token = _get_mpesa_token()
    resp  = requests.post(
        f"{_mpesa_base()}/mpesa/transactionstatus/v1/query",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    return {
        "accepted":          data.get("ResponseCode") == "0",
        "conversation_id":   data.get("ConversationID"),
        "response_code":     data.get("ResponseCode"),
        "description":       data.get("ResponseDescription"),
        "note":              "Result delivered asynchronously to MPESA_RESULT_URL",
    }


# ── Africa's Talking tools ────────────────────────────────────────────────────

@mcp.tool(annotations={
    'title': 'Send SMS',
    'readOnlyHint': False,
    'destructiveHint': True,
    'idempotentHint': False,
    'openWorldHint': True,
})
def sms_send(
    message: Annotated[str, "SMS message text. Unicode supported (Kiswahili, etc.)"],
    recipients: Annotated[list[str], "List of phone numbers in E.164 format e.g. ['+254712345678']"],
    sender_id: Annotated[str, "Optional pre-registered alphanumeric sender ID"] = "",
) -> dict:
    """
    Send SMS to one or many recipients via Africa's Talking.
    Supports up to 1,000 recipients per call.
    Works across Kenya, Nigeria, Ghana, Tanzania, Uganda, and 15+ African markets.
    Returns per-recipient status and cost.
    """
    sms = _at_sms()
    kwargs: dict = {"message": message, "recipients": recipients}
    if sender_id:
        kwargs["sender_id"] = sender_id

    response = sms.send(**kwargs)
    data      = response["SMSMessageData"]
    results   = data["Recipients"]

    success_count = sum(1 for r in results if r["status"] == "Success")
    failed        = [
        {"number": r["number"], "status": r["status"]}
        for r in results if r["status"] != "Success"
    ]

    return {
        "sent":     success_count,
        "failed":   len(failed),
        "failures": failed,
        "summary":  data.get("Message", ""),
        "results":  [
            {"number": r["number"], "status": r["status"], "cost": r.get("cost"), "id": r.get("messageId")}
            for r in results
        ],
    }


@mcp.tool(annotations={
    'title': 'Send Airtime',
    'readOnlyHint': False,
    'destructiveHint': True,
    'idempotentHint': False,
    'openWorldHint': True,
})
def airtime_send(
    phone: Annotated[str, "Recipient phone in E.164 format e.g. '+254712345678'"],
    amount: Annotated[str, "Amount as string e.g. '50' (KES 50). Minimum KES 10 in production."],
    currency_code: Annotated[str, "ISO currency code: KES, NGN, GHS, UGX, TZS, RWF, ZAR"] = "KES",
) -> dict:
    """
    Send airtime top-up to any MTN/Safaricom/Airtel/Vodafone subscriber.
    Common use: NGO field incentives, survey rewards, agent payouts.
    No real airtime sent in sandbox mode.
    """
    at = _at_airtime()
    response = at.send(phone_number=phone, amount=amount, currency_code=currency_code)
    recipients = response.get("responses", [])

    if recipients:
        r = recipients[0]
        return {
            "success":    r.get("status") == "Success",
            "status":     r.get("status"),
            "amount":     r.get("amount"),
            "request_id": r.get("requestId"),
            "error":      r.get("errorMessage") if r.get("status") != "Success" else None,
        }

    return {"success": False, "error": "No response from API", "raw": response}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
