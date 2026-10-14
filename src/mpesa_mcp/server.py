"""
mpesa-mcp — MCP server for East African fintech APIs  v0.2.0

Tools — M-Pesa (Safaricom Daraja):
  PAYMENTS
    mpesa_stk_push              — trigger Lipa Na M-Pesa payment prompt
    mpesa_stk_query             — check STK Push status
    mpesa_b2c                   — business disbursement to phone
    mpesa_business_paybill      — B2B payment to paybill number
    mpesa_business_buygoods     — B2B payment to till number
    mpesa_business_pochi        — pay to Pochi la Biashara wallet

  QUERIES
    mpesa_transaction_status    — query any transaction by receipt
    mpesa_account_balance       — query shortcode balance
    mpesa_stk_query             — check STK push status
    mpesa_pull_transactions     — pull C2B reconciliation records
    mpesa_query_org_info        — validate a shortcode name/tariff

  OPERATIONS
    mpesa_reversal              — reverse a transaction
    mpesa_dynamic_qr            — generate Dynamic QR code
    mpesa_tax_remittance        — remit tax to KRA
    mpesa_b2b_express_checkout  — USSD push to till (merchant-to-merchant)

  STANDING ORDERS
    mpesa_ratiba_create         — create M-PESA Ratiba standing order

  BILL MANAGER
    mpesa_bill_manager_optin    — enrol business in Bill Manager
    mpesa_bill_manager_invoice  — create invoice for customer
    mpesa_bill_manager_cancel   — cancel outstanding invoice

  IDENTITY / FRAUD
    mpesa_sim_swap_query        — detect recent SIM swap (fraud signal)
    mpesa_imsi_query            — verify phone registration details

Tools — Africa's Talking:
    sms_send                    — SMS to 1-1000 recipients, 15+ markets
    airtime_send                — airtime top-up, 20+ networks
"""

import base64
import datetime
import hashlib
import logging
import os
import re
import time
from typing import Annotated

import africastalking
import requests
from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s mpesa-mcp %(message)s")
_log = logging.getLogger("mpesa_mcp")


def _audit(tool, params, outcome):
    safe = {
        k: (hashlib.sha256(str(v).encode()).hexdigest()[:8] + "..." if k in {"phone", "party_a", "party_b", "phone_number"} else str(v))
        for k, v in params.items()
    }
    _log.info("TOOL=%s PARAMS=%s OUTCOME=%s", tool, safe, outcome)


# Annotations tell clients which tools are safe to auto-approve (read-only, no side effects).
READ_ONLY = {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False}

mcp = FastMCP(
    name="mpesa-mcp",
    instructions=(
        "Tools for M-Pesa (Safaricom Daraja) and Africa's Talking APIs. "
        "Covers Kenya mobile payments — STK Push, B2C, B2B, reversals, QR codes, "
        "standing orders, Bill Manager, SIM swap detection — and SMS/airtime across Africa. "
        "Set MPESA_SANDBOX=true for testing. No real money moves in sandbox mode."
    ),
)

# ── Auth & helpers ────────────────────────────────────────────────────────────

_token_cache: dict = {"token": None, "expires_at": 0.0}


def _get_mpesa_token() -> str:
    if time.time() < _token_cache["expires_at"] - 30:
        return _token_cache["token"]  # type: ignore[return-value]
    sandbox = os.environ.get("MPESA_SANDBOX", "true").lower() == "true"
    base = "https://sandbox.safaricom.co.ke" if sandbox else "https://api.safaricom.co.ke"
    key = os.environ["MPESA_CONSUMER_KEY"]
    secret = os.environ["MPESA_CONSUMER_SECRET"]
    creds = base64.b64encode(f"{key}:{secret}".encode()).decode()
    resp = requests.get(
        f"{base}/oauth/v1/generate?grant_type=client_credentials",
        headers={"Authorization": f"Basic {creds}"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = time.time() + int(data["expires_in"])
    return _token_cache["token"]  # type: ignore[return-value]


# ── Bounded authorization for tools that send money OUT ────────────────────────────────────────────────────────────────────────────────
# A language model can be talked into paying anyone any amount (prompt injection against payment tools is a documented attack on agent payment
# protocols). In LIVE mode these tools therefore need the user's explicit approval (confirm_send=true) and stay under a per-transaction cap.
DEFAULT_LIVE_CAP_KES = 100_000


def _is_sandbox() -> bool:
    return os.environ.get("MPESA_SANDBOX", "true").lower() == "true"


def _max_amount() -> int:
    """MPESA_MAX_AMOUNT_KES: per-transaction cap in live mode (default 100,000; 0 or 'none' = no cap, an explicit opt-out)."""
    raw = os.environ.get("MPESA_MAX_AMOUNT_KES", "").strip().lower()
    if not raw:
        return DEFAULT_LIVE_CAP_KES
    if raw in ("0", "none", "unlimited"):
        return 0
    try:
        return max(int(raw), 0)
    except ValueError:
        return DEFAULT_LIVE_CAP_KES


def _guard(tool: str, amount, confirm_send: bool):
    """None if the call may proceed; otherwise the refusal to return to the model. The sandbox is never restricted."""
    if _is_sandbox():
        return None
    try:
        value = float(amount)
    except (TypeError, ValueError):
        value = -1
    if value <= 0:
        _audit(tool, {"amount": amount}, "BLOCKED_INVALID_AMOUNT")
        return {"success": False, "sandbox": False, "error": "Amount must be a positive number."}
    if os.environ.get("MPESA_REQUIRE_CONFIRMATION", "true").lower() != "false" and confirm_send is not True:
        _audit(tool, {"amount": amount}, "BLOCKED_NO_CONFIRMATION")
        return {"success": False, "sandbox": False, "error": "Confirmation required: this tool sends money out of the business account. Show the user the recipient and amount, and call again with confirm_send=true only after they explicitly approve."}
    cap = _max_amount()
    if cap and value > cap:
        _audit(tool, {"amount": amount}, "BLOCKED_OVER_CAP")
        return {"success": False, "sandbox": False, "error": f"Amount {value:,.0f} exceeds the per-transaction cap of KES {cap:,}. An operator can change it with MPESA_MAX_AMOUNT_KES (0 = no cap)."}
    return None



DEFAULT_SMS_RECIPIENT_CAP = 50


def _max_sms_recipients() -> int:
    """MPESA_MAX_SMS_RECIPIENTS: per-call recipient cap in live mode (default 50; 0 or 'none' = no cap, an explicit opt-out)."""
    raw = os.environ.get("MPESA_MAX_SMS_RECIPIENTS", "").strip().lower()
    if not raw:
        return DEFAULT_SMS_RECIPIENT_CAP
    if raw in ("0", "none", "unlimited"):
        return 0
    try:
        return max(int(raw), 0)
    except ValueError:
        return DEFAULT_SMS_RECIPIENT_CAP


def _guard_sms(recipients, confirm_send: bool):
    """None if the SMS may be sent; otherwise the refusal to return to the model. The sandbox is never restricted.
    A model can be talked into messaging anyone (spam, phishing), so in LIVE mode a send needs the user's approval and a recipient cap."""
    if _is_sandbox():
        return None
    count = len(recipients) if isinstance(recipients, (list, tuple)) else 0
    if count == 0:
        _audit("sms_send", {"recipients": count}, "BLOCKED_NO_RECIPIENTS")
        return {"success": False, "sandbox": False, "error": "recipients must be a non-empty list."}
    if os.environ.get("MPESA_REQUIRE_CONFIRMATION", "true").lower() != "false" and confirm_send is not True:
        _audit("sms_send", {"recipients": count}, "BLOCKED_NO_CONFIRMATION")
        return {"success": False, "sandbox": False, "error": "Confirmation required: this tool sends SMS to real people. Show the user the message and the recipients, and call again with confirm_send=true only after they approve."}
    cap = _max_sms_recipients()
    if cap and count > cap:
        _audit("sms_send", {"recipients": count}, "BLOCKED_OVER_CAP")
        return {"success": False, "sandbox": False, "error": f"{count} recipients exceeds the per-call cap of {cap}. An operator can change it with MPESA_MAX_SMS_RECIPIENTS (0 = no cap)."}
    return None


def _mpesa_base() -> str:
    sandbox = os.environ.get("MPESA_SANDBOX", "true").lower() == "true"
    return "https://sandbox.safaricom.co.ke" if sandbox else "https://api.safaricom.co.ke"


def _normalize_phone(phone: str) -> str:
    phone = phone.strip().lstrip("+")
    if phone.startswith("0"):
        phone = "254" + phone[1:]
    elif not phone.startswith("254"):
        phone = "254" + phone
    return phone


def _stk_password(shortcode: str, passkey: str, ts: str) -> str:
    return base64.b64encode(f"{shortcode}{passkey}{ts}".encode()).decode()


def _callback() -> str:
    return os.environ["MPESA_CALLBACK_URL"]


def _result_url() -> str:
    return os.environ.get("MPESA_RESULT_URL", _callback())


def _timeout_url() -> str:
    return os.environ.get("MPESA_TIMEOUT_URL", _callback())


def _at_init():
    africastalking.initialize(username=os.environ["AT_USERNAME"], api_key=os.environ["AT_API_KEY"])


# ── PAYMENTS ─────────────────────────────────────────────────────────────────

@mcp.tool(description="Send an M-PESA payment prompt (STK Push) to a customer's phone for them to approve with their PIN. Use when a customer is to pay your business shortcode. The customer must approve on the handset: nothing is taken without their PIN. Returns success, checkout_request_id, merchant_request_id, response code, message and the sandbox flag; success means the prompt was SENT, not that the customer paid, so poll mpesa_stk_query. In live mode it prompts a real phone.", annotations={"title": "M-Pesa STK Push", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
def mpesa_stk_push(
    phone: Annotated[str, "Customer phone (any Kenyan format: +254..., 07..., 254...)"],
    amount: Annotated[int, "Amount in KES (whole number, min 1, max 150000)"],
    account_ref: Annotated[str, "Account reference shown to customer on phone (max 12 chars)"],
    description: Annotated[str, "Transaction description (max 13 chars)"] = "Payment",
) -> dict:
    """
    Trigger M-Pesa STK Push — sends payment prompt to customer's phone.
    Customer enters M-PESA PIN to complete payment.
    Returns CheckoutRequestID; poll mpesa_stk_query after 10-30 seconds.
    """
    if not 1 <= amount <= 150_000:
        return {"error": f"Amount {amount} out of bounds [1, 150000]"}
    shortcode = os.environ["MPESA_SHORTCODE"]
    passkey = os.environ["MPESA_PASSKEY"]
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    phone = _normalize_phone(phone)
    _audit("mpesa_stk_push", {"phone": phone, "amount": amount}, "INITIATED")
    token = _get_mpesa_token()
    resp = requests.post(
        f"{_mpesa_base()}/mpesa/stkpush/v1/processrequest",
        json={
            "BusinessShortCode": shortcode,
            "Password": _stk_password(shortcode, passkey, ts),
            "Timestamp": ts,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone,
            "PartyB": shortcode,
            "PhoneNumber": phone,
            "CallBackURL": _callback(),
            "AccountReference": account_ref[:12],
            "TransactionDesc": description[:13],
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "success": data.get("ResponseCode") == "0",
        "checkout_request_id": data.get("CheckoutRequestID"),
        "merchant_request_id": data.get("MerchantRequestID"),
        "response_code": data.get("ResponseCode"),
        "message": data.get("CustomerMessage", data.get("ResponseDescription")),
        "sandbox": os.environ.get("MPESA_SANDBOX", "true").lower() == "true",
    }


@mcp.tool(description="Check the status of an STK Push using its checkout_request_id. Use 10 to 30 seconds after mpesa_stk_push to learn whether the customer paid, cancelled or the request is still processing. Returns the Daraja status for that request with the sandbox flag. Read-only.", annotations={"title": "M-Pesa STK Query", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
def mpesa_stk_query(
    checkout_request_id: Annotated[str, "CheckoutRequestID from mpesa_stk_push response"],
) -> dict:
    """
    Check STK Push status. Poll 10-30s after mpesa_stk_push.
    ResultCode 0 = success, 1032 = cancelled, 1037 = timed out.

    IMPORTANT: Daraja's STK Push has a ~60s window and the callback is NOT
    guaranteed to fire if the user dismisses the prompt. Poll this tool 2-3
    times across that window before treating silence as failure — a single
    empty response does not mean the payment failed.
    """
    shortcode = os.environ["MPESA_SHORTCODE"]
    passkey = os.environ["MPESA_PASSKEY"]
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    token = _get_mpesa_token()
    resp = requests.post(
        f"{_mpesa_base()}/mpesa/stkpushquery/v1/query",
        json={"BusinessShortCode": shortcode, "Password": _stk_password(shortcode, passkey, ts), "Timestamp": ts, "CheckoutRequestID": checkout_request_id},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    rc = int(data.get("ResultCode", -1))
    status_map = {0: "SUCCESS", 1: "INSUFFICIENT_FUNDS", 1001: "LOCKED", 1019: "EXPIRED", 1032: "CANCELLED_BY_USER", 1037: "TIMEOUT", 2001: "WRONG_PIN"}
    return {"success": rc == 0, "result_code": rc, "status": status_map.get(rc, f"UNKNOWN({rc})"), "description": data.get("ResultDesc")}


@mcp.tool(description="Send money from your business shortcode to a customer's phone (Business to Customer). Use only when the user has explicitly approved this exact payment. MOVES MONEY: in live mode it needs confirm_send=true (set only after the user approves this exact payment) and refuses amounts above the per-transaction cap (MPESA_MAX_AMOUNT_KES, default KES 100,000); the sandbox is never restricted. Returns success, the Daraja response and the sandbox flag, or a refusal saying what is missing; the final result arrives asynchronously on your result URL.", annotations={"title": "M-Pesa B2C", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
def mpesa_b2c(
    phone: Annotated[str, "Recipient phone number (any Kenyan format)"],
    amount: Annotated[int, "Amount in KES to send"],
    command_id: Annotated[str, "SalaryPayment | BusinessPayment | PromotionPayment"] = "BusinessPayment",
    remarks: Annotated[str, "Remarks (max 100 chars)"] = "B2C via mpesa-mcp",
    occasion: Annotated[str, "Optional occasion label"] = "",
    confirm_send: Annotated[bool, "Required in live mode: set true ONLY after the user has explicitly approved this exact payment (recipient and amount). Ignored in sandbox."] = False,
) -> dict:
    """
    Business To Customer disbursement — send money from shortcode to phone.
    Use for payroll, NGO field incentives, agent float, survey rewards.
    Result delivered async to MPESA_RESULT_URL.
    Requires MPESA_INITIATOR_NAME and MPESA_SECURITY_CREDENTIAL env vars.
    """
    blocked = _guard("mpesa_b2c", amount, confirm_send)
    if blocked:
        return blocked
    phone = _normalize_phone(phone)
    _audit("mpesa_b2c", {"phone": phone, "amount": amount}, "INITIATED")
    token = _get_mpesa_token()
    resp = requests.post(
        f"{_mpesa_base()}/mpesa/b2c/v3/paymentrequest",
        json={
            "InitiatorName": os.environ["MPESA_INITIATOR_NAME"],
            "SecurityCredential": os.environ["MPESA_SECURITY_CREDENTIAL"],
            "CommandID": command_id,
            "Amount": amount,
            "PartyA": os.environ["MPESA_SHORTCODE"],
            "PartyB": phone,
            "Remarks": remarks[:100],
            "QueueTimeOutURL": _timeout_url(),
            "ResultURL": _result_url(),
            "Occasion": occasion,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "accepted": data.get("ResponseCode") == "0",
        "conversation_id": data.get("ConversationID"),
        "originator_id": data.get("OriginatorConversationID"),
        "response_code": data.get("ResponseCode"),
        "description": data.get("ResponseDescription"),
        "note": "Funds sent async — result delivered to MPESA_RESULT_URL",
    }


@mcp.tool(description="Pay from your business shortcode directly to another paybill number (B2B PayBill). Use only when the user has explicitly approved this exact payment. MOVES MONEY: in live mode it needs confirm_send=true (set only after the user approves this exact payment) and refuses amounts above the per-transaction cap (MPESA_MAX_AMOUNT_KES, default KES 100,000); the sandbox is never restricted. Returns success, the Daraja response and the sandbox flag, or a refusal saying what is missing; the final result arrives asynchronously on your result URL.", annotations={"title": "Business Pay Bill (B2B)", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
def mpesa_business_paybill(
    receiver_paybill: Annotated[str, "Destination paybill shortcode"],
    amount: Annotated[int, "Amount in KES"],
    account_reference: Annotated[str, "Account number at destination paybill"],
    remarks: Annotated[str, "Transaction remarks"] = "B2B PayBill via mpesa-mcp",
    confirm_send: Annotated[bool, "Required in live mode: set true ONLY after the user has explicitly approved this exact payment (recipient and amount). Ignored in sandbox."] = False,
) -> dict:
    """
    Pay directly from business shortcode to another paybill number.
    Use for supplier payments, utility bills, inter-business transfers.
    Requires MPESA_INITIATOR_NAME and MPESA_SECURITY_CREDENTIAL.
    """
    blocked = _guard("mpesa_business_paybill", amount, confirm_send)
    if blocked:
        return blocked
    _audit("mpesa_business_paybill", {"receiver": receiver_paybill, "amount": amount}, "INITIATED")
    token = _get_mpesa_token()
    resp = requests.post(
        f"{_mpesa_base()}/mpesa/b2b/v1/paymentrequest",
        json={
            "Initiator": os.environ["MPESA_INITIATOR_NAME"],
            "SecurityCredential": os.environ["MPESA_SECURITY_CREDENTIAL"],
            "CommandID": "BusinessPayBill",
            "SenderIdentifierType": "4",
            "RecieverIdentifierType": "4",
            "Amount": amount,
            "PartyA": os.environ["MPESA_SHORTCODE"],
            "PartyB": receiver_paybill,
            "AccountReference": account_reference,
            "Remarks": remarks,
            "QueueTimeOutURL": _timeout_url(),
            "ResultURL": _result_url(),
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return {"accepted": data.get("ResponseCode") == "0", "conversation_id": data.get("ConversationID"), "description": data.get("ResponseDescription")}


@mcp.tool(description="Pay from your business shortcode to a till (Buy Goods) number. Use only when the user has explicitly approved this exact payment. MOVES MONEY: in live mode it needs confirm_send=true (set only after the user approves this exact payment) and refuses amounts above the per-transaction cap (MPESA_MAX_AMOUNT_KES, default KES 100,000); the sandbox is never restricted. Returns success, the Daraja response and the sandbox flag, or a refusal saying what is missing; the final result arrives asynchronously on your result URL.", annotations={"title": "Business Buy Goods (B2B)", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
def mpesa_business_buygoods(
    till_number: Annotated[str, "Destination till number (Buy Goods)"],
    amount: Annotated[int, "Amount in KES"],
    remarks: Annotated[str, "Transaction remarks"] = "B2B BuyGoods via mpesa-mcp",
    confirm_send: Annotated[bool, "Required in live mode: set true ONLY after the user has explicitly approved this exact payment (recipient and amount). Ignored in sandbox."] = False,
) -> dict:
    """
    Pay from business shortcode to a till/buy-goods number.
    Requires MPESA_INITIATOR_NAME and MPESA_SECURITY_CREDENTIAL.
    """
    blocked = _guard("mpesa_business_buygoods", amount, confirm_send)
    if blocked:
        return blocked
    _audit("mpesa_business_buygoods", {"till": till_number, "amount": amount}, "INITIATED")
    token = _get_mpesa_token()
    resp = requests.post(
        f"{_mpesa_base()}/mpesa/b2b/v1/paymentrequest",
        json={
            "Initiator": os.environ["MPESA_INITIATOR_NAME"],
            "SecurityCredential": os.environ["MPESA_SECURITY_CREDENTIAL"],
            "CommandID": "BusinessBuyGoods",
            "SenderIdentifierType": "4",
            "RecieverIdentifierType": "2",
            "Amount": amount,
            "PartyA": os.environ["MPESA_SHORTCODE"],
            "PartyB": till_number,
            "AccountReference": till_number,
            "Remarks": remarks,
            "QueueTimeOutURL": _timeout_url(),
            "ResultURL": _result_url(),
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return {"accepted": data.get("ResponseCode") == "0", "conversation_id": data.get("ConversationID"), "description": data.get("ResponseDescription")}


@mcp.tool(description="Pay from your business shortcode to a Pochi la Biashara micro-business wallet by phone number. Use only when the user has explicitly approved this exact payment. MOVES MONEY: in live mode it needs confirm_send=true (set only after the user approves this exact payment) and refuses amounts above the per-transaction cap (MPESA_MAX_AMOUNT_KES, default KES 100,000); the sandbox is never restricted. Returns success, the Daraja response and the sandbox flag, or a refusal saying what is missing; the final result arrives asynchronously on your result URL.", annotations={"title": "Business to Pochi la Biashara", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
def mpesa_business_pochi(
    phone: Annotated[str, "Pochi wallet owner phone number"],
    amount: Annotated[int, "Amount in KES"],
    remarks: Annotated[str, "Remarks"] = "Pochi payment via mpesa-mcp",
    confirm_send: Annotated[bool, "Required in live mode: set true ONLY after the user has explicitly approved this exact payment (recipient and amount). Ignored in sandbox."] = False,
) -> dict:
    """
    Pay from business shortcode to a Pochi la Biashara micro-SME wallet.
    Used for micro-enterprise supplier payments and informal sector settlements.
    Requires MPESA_INITIATOR_NAME and MPESA_SECURITY_CREDENTIAL.
    """
    blocked = _guard("mpesa_business_pochi", amount, confirm_send)
    if blocked:
        return blocked
    phone = _normalize_phone(phone)
    _audit("mpesa_business_pochi", {"phone": phone, "amount": amount}, "INITIATED")
    token = _get_mpesa_token()
    resp = requests.post(
        f"{_mpesa_base()}/mpesa/b2c/v3/paymentrequest",
        json={
            "InitiatorName": os.environ["MPESA_INITIATOR_NAME"],
            "SecurityCredential": os.environ["MPESA_SECURITY_CREDENTIAL"],
            "CommandID": "BusinessPayToBulk",
            "Amount": amount,
            "PartyA": os.environ["MPESA_SHORTCODE"],
            "PartyB": phone,
            "Remarks": remarks,
            "QueueTimeOutURL": _timeout_url(),
            "ResultURL": _result_url(),
            "Occasion": "PochiPayment",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return {"accepted": data.get("ResponseCode") == "0", "conversation_id": data.get("ConversationID"), "description": data.get("ResponseDescription")}


# ── QUERIES ───────────────────────────────────────────────────────────────────

@mcp.tool(description="Query the status of any M-PESA transaction by its receipt number. Use when you need to confirm what happened to a payment, or to reconcile one against your records after an STK Push, B2C or reversal. Returns the Daraja response for that transaction, whose full details can arrive asynchronously on your result URL. Read-only; it changes nothing.", annotations={"title": "M-Pesa Transaction Status", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
def mpesa_transaction_status(
    transaction_id: Annotated[str, "M-Pesa receipt number e.g. QKL8XXXXXX"],
) -> dict:
    """
    Query status of any M-Pesa transaction by receipt number.
    Requires MPESA_INITIATOR_NAME and MPESA_SECURITY_CREDENTIAL.
    Result delivered async to MPESA_RESULT_URL.
    """
    token = _get_mpesa_token()
    resp = requests.post(
        f"{_mpesa_base()}/mpesa/transactionstatus/v1/query",
        json={
            "Initiator": os.environ["MPESA_INITIATOR_NAME"],
            "SecurityCredential": os.environ["MPESA_SECURITY_CREDENTIAL"],
            "CommandID": "TransactionStatusQuery",
            "TransactionID": transaction_id,
            "PartyA": os.environ["MPESA_SHORTCODE"],
            "IdentifierType": "4",
            "ResultURL": _result_url(),
            "QueueTimeOutURL": _timeout_url(),
            "Remarks": "Status query via mpesa-mcp",
            "Occasion": "",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return {"accepted": data.get("ResponseCode") == "0", "conversation_id": data.get("ConversationID"), "description": data.get("ResponseDescription"), "note": "Result async to MPESA_RESULT_URL"}


@mcp.tool(description="Query the balance of your business M-PESA account (shortcode or till). Use when someone asks how much is in the account. identifier_type 4 (default) means an organisation shortcode. Returns the Daraja response, with the balance delivered on your result URL. Read-only.", annotations={"title": "M-Pesa Account Balance", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
def mpesa_account_balance(
    identifier_type: Annotated[str, "1=MSISDN, 2=Till, 4=Shortcode/Paybill"] = "4",
    remarks: Annotated[str, "Query remarks"] = "Balance query via mpesa-mcp",
) -> dict:
    """
    Query current balance of the business M-Pesa account (shortcode/till).
    Result delivered async to MPESA_RESULT_URL.
    Requires MPESA_INITIATOR_NAME and MPESA_SECURITY_CREDENTIAL.
    """
    token = _get_mpesa_token()
    resp = requests.post(
        f"{_mpesa_base()}/mpesa/accountbalance/v1/query",
        json={
            "Initiator": os.environ["MPESA_INITIATOR_NAME"],
            "SecurityCredential": os.environ["MPESA_SECURITY_CREDENTIAL"],
            "CommandID": "AccountBalance",
            "PartyA": os.environ["MPESA_SHORTCODE"],
            "IdentifierType": identifier_type,
            "Remarks": remarks,
            "QueueTimeOutURL": _timeout_url(),
            "ResultURL": _result_url(),
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return {"accepted": data.get("ResponseCode") == "0", "conversation_id": data.get("ConversationID"), "description": data.get("ResponseDescription"), "note": "Balance delivered async to MPESA_RESULT_URL"}


@mcp.tool(description="Validate a shortcode and return its registered organisation name and tariff type. Use before paying a paybill or till to confirm who will actually receive the money, which helps catch a mistyped number or a lookalike business name. Returns the Daraja organisation details (registered name and tariff type). Read-only; it changes nothing.", annotations={"title": "Query Org Info", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
def mpesa_query_org_info(
    shortcode: Annotated[str, "Shortcode to validate (paybill or till number)"],
) -> dict:
    """
    Validate a shortcode — returns the registered name and tariff type.
    Use before sending B2B payments to confirm the destination shortcode is correct.
    Prevents accidental payments to wrong paybill numbers.
    """
    token = _get_mpesa_token()
    resp = requests.get(
        f"{_mpesa_base()}/v1/info/details/{shortcode}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "shortcode": shortcode,
        "name": data.get("OrganizationName", data.get("name")),
        "tariff": data.get("TariffDetails", data.get("tariff")),
        "type": data.get("ShortCodeType", data.get("type")),
        "valid": resp.status_code == 200,
        "raw": data,
    }


@mcp.tool(description="Pull C2B transactions in a date range for reconciliation. Use when reconciling payments received. start_date and end_date use YYYY-MM-DD HH:MM:SS; offset pages through results from 0. Returns count, the transactions, the response code and message. Read-only.", annotations={"title": "Pull C2B Transactions", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
def mpesa_pull_transactions(
    start_date: Annotated[str, "Start date YYYY-MM-DD HH:MM:SS"],
    end_date: Annotated[str, "End date YYYY-MM-DD HH:MM:SS"],
    offset: Annotated[int, "Pagination offset (0-based)"] = 0,
) -> dict:
    """
    Pull all C2B transactions for reconciliation within a date range.
    Returns customer payments to your shortcode for audit and reconciliation.
    Max range: 48 hours per call. Max 10,000 records per call.
    """
    token = _get_mpesa_token()
    resp = requests.post(
        f"{_mpesa_base()}/pulltransactions/v1/query",
        json={
            "ShortCode": os.environ["MPESA_SHORTCODE"],
            "StartDate": start_date,
            "EndDate": end_date,
            "OffSetValue": str(offset),
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    transactions = data.get("Data", [])
    return {
        "count": len(transactions),
        "transactions": transactions,
        "response_code": data.get("ResponseCode"),
        "message": data.get("ResponseMessage"),
    }


# ── OPERATIONS ────────────────────────────────────────────────────────────────

@mcp.tool(description="Reverse an erroneous M-PESA transaction by its receipt number. Use only when the user has explicitly approved reversing this exact transaction. MOVES MONEY: in live mode it needs confirm_send=true (set only after the user approves this exact payment) and refuses amounts above the per-transaction cap (MPESA_MAX_AMOUNT_KES, default KES 100,000); the sandbox is never restricted. Returns success, the Daraja response and the sandbox flag, or a refusal saying what is missing; the final result arrives asynchronously on your result URL.", annotations={"title": "M-Pesa Reversal", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
def mpesa_reversal(
    transaction_id: Annotated[str, "M-Pesa receipt to reverse e.g. QKL8XXXXXX"],
    amount: Annotated[int, "Amount to reverse in KES"],
    remarks: Annotated[str, "Reason for reversal"] = "Reversal via mpesa-mcp",
    confirm_send: Annotated[bool, "Required in live mode: set true ONLY after the user has explicitly approved this exact payment (recipient and amount). Ignored in sandbox."] = False,
) -> dict:
    """
    Reverse an erroneous M-Pesa transaction.
    Use when a payment was sent to the wrong number or wrong amount.
    Requires MPESA_INITIATOR_NAME and MPESA_SECURITY_CREDENTIAL.
    Result delivered async to MPESA_RESULT_URL.
    """
    blocked = _guard("mpesa_reversal", amount, confirm_send)
    if blocked:
        return blocked
    _audit("mpesa_reversal", {"transaction_id": transaction_id, "amount": amount}, "INITIATED")
    token = _get_mpesa_token()
    resp = requests.post(
        f"{_mpesa_base()}/mpesa/reversal/v1/request",
        json={
            "Initiator": os.environ["MPESA_INITIATOR_NAME"],
            "SecurityCredential": os.environ["MPESA_SECURITY_CREDENTIAL"],
            "CommandID": "TransactionReversal",
            "TransactionID": transaction_id,
            "Amount": amount,
            "ReceiverParty": os.environ["MPESA_SHORTCODE"],
            "RecieverIdentifierType": "4",
            "ResultURL": _result_url(),
            "QueueTimeOutURL": _timeout_url(),
            "Remarks": remarks,
            "Occasion": "",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return {"accepted": data.get("ResponseCode") == "0", "conversation_id": data.get("ConversationID"), "description": data.get("ResponseDescription"), "note": "Result async to MPESA_RESULT_URL"}


@mcp.tool(description="Generate a dynamic M-PESA QR code for a specific amount and reference. Use when a customer should pay by scanning. Returns qr_base64 (a PNG), qr_data_url usable in an HTML img tag, and the merchant, amount and reference. The QR encodes the amount you pass, so check it before showing it to a customer. Read-only; it changes nothing.", annotations={"title": "Dynamic QR Code", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
def mpesa_dynamic_qr(
    merchant_name: Annotated[str, "Business/merchant name to display on QR"],
    amount: Annotated[int, "Amount in KES to encode in QR"],
    ref_no: Annotated[str, "Transaction reference number"],
    trx_code: Annotated[str, "BG=Buy Goods, PB=Paybill, WA=Wallet, SM=Send Money, SB=Lipa Shortcode"] = "PB",
    qr_size: Annotated[int, "QR image size in pixels (300-1000)"] = 400,
) -> dict:
    """
    Generate a Dynamic M-PESA QR code for a specific payment amount.
    Customer scans QR with their M-PESA app — amount pre-fills automatically.
    Returns base64-encoded QR image. Use for receipts, invoices, POS displays.
    """
    token = _get_mpesa_token()
    cpi = os.environ["MPESA_SHORTCODE"]
    resp = requests.post(
        f"{_mpesa_base()}/mpesa/qrcode/v1/generate",
        json={
            "MerchantName": merchant_name,
            "RefNo": ref_no,
            "Amount": str(amount),
            "TrxCode": trx_code,
            "CPI": cpi,
            "Size": str(qr_size),
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    qr_b64 = data.get("QRCode", "")
    return {
        "success": bool(qr_b64),
        "qr_base64": qr_b64,
        "qr_data_url": f"data:image/png;base64,{qr_b64}" if qr_b64 else None,
        "merchant": merchant_name,
        "amount": amount,
        "ref": ref_no,
        "note": "qr_base64 contains a PNG image. qr_data_url can be used in HTML <img src=>",
    }


@mcp.tool(description="Remit tax from your M-PESA business account to the Kenya Revenue Authority. Use only when the user has explicitly approved this exact remittance. MOVES MONEY: in live mode it needs confirm_send=true (set only after the user approves this exact payment) and refuses amounts above the per-transaction cap (MPESA_MAX_AMOUNT_KES, default KES 100,000); the sandbox is never restricted. Returns success, the Daraja response and the sandbox flag, or a refusal saying what is missing; the final result arrives asynchronously on your result URL.", annotations={"title": "Tax Remittance to KRA", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
def mpesa_tax_remittance(
    amount: Annotated[int, "Tax amount in KES"],
    account_reference: Annotated[str, "KRA Payment Registration Number (PRN)"],
    remarks: Annotated[str, "Remittance remarks"] = "Tax remittance via mpesa-mcp",
    confirm_send: Annotated[bool, "Required in live mode: set true ONLY after the user has explicitly approved this exact payment (recipient and amount). Ignored in sandbox."] = False,
) -> dict:
    """
    Remit tax directly from M-PESA business account to Kenya Revenue Authority.
    Provide the KRA Payment Registration Number (PRN) as account_reference.
    KRA shortcode: 572572. Requires MPESA_INITIATOR_NAME and MPESA_SECURITY_CREDENTIAL.
    """
    blocked = _guard("mpesa_tax_remittance", amount, confirm_send)
    if blocked:
        return blocked
    KRA_SHORTCODE = "572572"
    _audit("mpesa_tax_remittance", {"amount": amount, "prn": account_reference}, "INITIATED")
    token = _get_mpesa_token()
    resp = requests.post(
        f"{_mpesa_base()}/mpesa/b2b/v1/remittax",
        json={
            "Initiator": os.environ["MPESA_INITIATOR_NAME"],
            "SecurityCredential": os.environ["MPESA_SECURITY_CREDENTIAL"],
            "CommandID": "PayTaxToKRA",
            "SenderIdentifierType": "4",
            "RecieverIdentifierType": "4",
            "Amount": amount,
            "PartyA": os.environ["MPESA_SHORTCODE"],
            "PartyB": KRA_SHORTCODE,
            "AccountReference": account_reference,
            "Remarks": remarks,
            "QueueTimeOutURL": _timeout_url(),
            "ResultURL": _result_url(),
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return {"accepted": data.get("ResponseCode") == "0", "conversation_id": data.get("ConversationID"), "kra_shortcode": KRA_SHORTCODE, "prn": account_reference, "description": data.get("ResponseDescription")}


@mcp.tool(description="Start a B2B Express Checkout: a USSD push to another merchant's till so they approve a payment from your account. Use only when the user has explicitly approved this exact payment. MOVES MONEY: in live mode it needs confirm_send=true (set only after the user approves this exact payment) and refuses amounts above the per-transaction cap (MPESA_MAX_AMOUNT_KES, default KES 100,000); the sandbox is never restricted. Returns success, the Daraja response and the sandbox flag, or a refusal saying what is missing; the final result arrives asynchronously on your result URL.", annotations={"title": "B2B Express Checkout", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
def mpesa_b2b_express_checkout(
    receiver_till: Annotated[str, "Recipient till number"],
    amount: Annotated[int, "Amount in KES"],
    account_reference: Annotated[str, "Account reference for the transaction"],
    remarks: Annotated[str, "Remarks"] = "B2B Express via mpesa-mcp",
    confirm_send: Annotated[bool, "Required in live mode: set true ONLY after the user has explicitly approved this exact payment (recipient and amount). Ignored in sandbox."] = False,
) -> dict:
    """
    Initiate USSD Push to till — enables merchant-to-merchant payments.
    Recipient merchant receives a USSD prompt to confirm payment from their till.
    Use for wholesale supplier payments between Lipa Na M-PESA merchants.
    Requires MPESA_INITIATOR_NAME and MPESA_SECURITY_CREDENTIAL.
    """
    blocked = _guard("mpesa_b2b_express_checkout", amount, confirm_send)
    if blocked:
        return blocked
    _audit("mpesa_b2b_express", {"till": receiver_till, "amount": amount}, "INITIATED")
    token = _get_mpesa_token()
    resp = requests.post(
        f"{_mpesa_base()}/mpesa/b2b/v1/paymentrequest",
        json={
            "primaryShortCode": os.environ["MPESA_SHORTCODE"],
            "receiverShortCode": receiver_till,
            "amount": str(amount),
            "paymentRef": account_reference,
            "callbackUrl": _callback(),
            "partnerName": remarks,
            "RequestRefID": f"MEXP{int(time.time())}",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return {"accepted": data.get("responseCode") == "0", "conversation_id": data.get("conversationId"), "description": data.get("responseDescription")}


# ── STANDING ORDERS ───────────────────────────────────────────────────────────

@mcp.tool(description="Create an M-PESA Ratiba standing order: automated recurring payments collected from a customer's phone. Use when a customer wants to pay a regular amount. The customer must approve on their handset; confirm the amount, dates and customer with the user first, since this creates a recurring commitment. frequency 1 one-off, 2 daily, 3 weekly, 4 monthly (default), 5 bi-monthly, 6 quarterly, 7 half-year, 8 annually. Returns success, standing_order_id, response code, message and frequency_label.", annotations={"title": "M-PESA Ratiba — Create Standing Order", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
def mpesa_ratiba_create(
    standing_order_name: Annotated[str, "Name for the standing order"],
    start_date: Annotated[str, "Start date YYYYMMDD"],
    end_date: Annotated[str, "End date YYYYMMDD"],
    phone: Annotated[str, "Customer phone number"],
    amount: Annotated[int, "Amount in KES per payment"],
    account_ref: Annotated[str, "Account reference for each payment"],
    frequency: Annotated[str, "1=One-Off 2=Daily 3=Weekly 4=Monthly 5=Bi-Monthly 6=Quarterly 7=Half-Year 8=Annually"] = "4",
    description: Annotated[str, "Standing order description"] = "Standing order via mpesa-mcp",
) -> dict:
    """
    Create an M-PESA Ratiba standing order — automated recurring payments.
    Customer authorizes once; payments happen automatically on schedule.
    Perfect for subscription billing, rent collection, loan repayments, SACCO contributions.
    Returns a standing order ID to manage/cancel later.
    """
    phone = _normalize_phone(phone)
    _audit("mpesa_ratiba_create", {"phone": phone, "amount": amount, "frequency": frequency}, "INITIATED")
    shortcode = os.environ["MPESA_SHORTCODE"]
    passkey = os.environ["MPESA_PASSKEY"]
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    token = _get_mpesa_token()
    resp = requests.post(
        f"{_mpesa_base()}/v1/ratiba/create",
        json={
            "StandingOrderName": standing_order_name,
            "StartDate": start_date,
            "EndDate": end_date,
            "BusinessShortCode": shortcode,
            "TransactionType": "Standing Order Customer Pay Bill",
            "ReceiverPartyIdentifierType": "4",
            "Amount": amount,
            "PartyA": phone,
            "PartyB": shortcode,
            "AccountReference": account_ref,
            "TransactionDesc": description[:13],
            "Frequency": frequency,
            "CallBackURL": _callback(),
            "Password": _stk_password(shortcode, passkey, ts),
            "Timestamp": ts,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "success": data.get("ResponseCode") == "0",
        "standing_order_id": data.get("StandingOrderId", data.get("CheckoutRequestID")),
        "response_code": data.get("ResponseCode"),
        "message": data.get("CustomerMessage", data.get("ResponseDescription")),
        "frequency_label": {"1": "One-Off", "2": "Daily", "3": "Weekly", "4": "Monthly", "5": "Bi-Monthly", "6": "Quarterly", "7": "Half-Year", "8": "Annually"}.get(frequency, frequency),
    }


# ── BILL MANAGER ─────────────────────────────────────────────────────────────

@mcp.tool(description="Enrol your business in M-PESA Bill Manager, a one-time setup for sending invoices with payment links. Use before creating invoices. Takes the notification email and an optional logo and callback URL. Returns the Daraja response. Changes your Bill Manager registration.", annotations={"title": "Bill Manager — Opt In", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
def mpesa_bill_manager_optin(
    email: Annotated[str, "Business email for Bill Manager notifications"],
    logo_url: Annotated[str, "HTTPS URL to your business logo (PNG/JPG)"] = "",
    callback_url: Annotated[str, "Callback URL for Bill Manager events"] = "",
) -> dict:
    """
    Enrol your business in M-PESA Bill Manager.
    Must be called once before creating invoices.
    After opt-in, customers can pay your invoices directly via M-PESA.
    """
    token = _get_mpesa_token()
    resp = requests.post(
        f"{_mpesa_base()}/v1/billmanager-invoice/optin",
        json={
            "shortcode": os.environ["MPESA_SHORTCODE"],
            "email": email,
            "officialContact": os.environ.get("MPESA_OFFICIAL_CONTACT", ""),
            "sendReminders": "1",
            "logo": logo_url,
            "callbackurl": callback_url or _callback(),
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return {"success": data.get("rescode") == "200", "message": data.get("resmsg"), "raw": data}


@mcp.tool(description="Create a Bill Manager invoice: the customer receives an SMS with the amount and a way to pay. Use when billing a customer. Sends an SMS to the customer's phone in live mode, so have the user approve the customer, amount and due date first. Returns the Daraja response for the invoice.", annotations={"title": "Bill Manager — Create Invoice", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
def mpesa_bill_manager_invoice(
    external_ref: Annotated[str, "Your internal invoice/reference number"],
    billing_ref: Annotated[str, "Customer billing account reference"],
    invoice_name: Annotated[str, "Invoice description shown to customer"],
    amount: Annotated[float, "Invoice amount in KES"],
    due_date: Annotated[str, "Payment due date YYYY-MM-DD"],
    phone: Annotated[str, "Customer phone to receive SMS notification"],
    account_ref: Annotated[str, "Account reference for the payment"] = "",
) -> dict:
    """
    Create a Bill Manager invoice — customer receives SMS with payment link.
    They can pay directly via M-PESA by clicking the link or using the paybill.
    Returns invoice ID. Use mpesa_bill_manager_cancel to void outstanding invoices.
    """
    phone = _normalize_phone(phone)
    _audit("mpesa_bill_manager_invoice", {"phone": phone, "amount": amount, "ref": external_ref}, "INITIATED")
    token = _get_mpesa_token()
    resp = requests.post(
        f"{_mpesa_base()}/v1/billmanager-invoice/single-invoicing",
        json={
            "externalReference": external_ref,
            "billingRef": billing_ref,
            "invoiceName": invoice_name,
            "invoiceItems": [],
            "amount": str(amount),
            "accountReference": account_ref or billing_ref,
            "invoiceDueDate": due_date,
            "sendReminders": True,
            "remindersSendTimes": 1,
            "dueReminder": "0",
            "ReceiverPhoneNumber": phone,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return {"success": data.get("rescode") == "200", "invoice_id": external_ref, "message": data.get("resmsg"), "customer_phone": phone}


@mcp.tool(description="Cancel an outstanding Bill Manager invoice by its external reference. Use when an invoice was raised in error or is no longer due. Returns the Daraja response. Cancels the invoice, so have the user approve it first; the customer will no longer be able to pay it, and a cancelled invoice cannot be restored through this tool.", annotations={"title": "Bill Manager — Cancel Invoice", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": True})
def mpesa_bill_manager_cancel(
    external_reference: Annotated[str, "The externalReference used when creating the invoice"],
) -> dict:
    """
    Cancel an outstanding Bill Manager invoice.
    Customer will no longer be able to pay the cancelled invoice.
    Use when an order is cancelled or a duplicate invoice was created.
    """
    _audit("mpesa_bill_manager_cancel", {"ref": external_reference}, "INITIATED")
    token = _get_mpesa_token()
    resp = requests.post(
        f"{_mpesa_base()}/v1/billmanager-invoice/cancel-single-invoice",
        json={"externalReference": external_reference},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return {"success": data.get("rescode") == "200", "cancelled_ref": external_reference, "message": data.get("resmsg")}


# ── IDENTITY / FRAUD PREVENTION ───────────────────────────────────────────────

@mcp.tool(description="Check whether a phone number's SIM was recently swapped, a fraud signal before sending money. Use before a disbursement to an unfamiliar or high-value recipient. This queries personal data about a subscriber: do so only with a lawful basis and any consent required under the Data Protection Act 2019. Returns phone, swap_detected, last_swap_date, a risk level (HIGH if swapped) and a recommendation. Read-only.", annotations={"title": "SIM Swap Query", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
def mpesa_sim_swap_query(
    phone: Annotated[str, "Phone number to check for SIM swap activity"],
) -> dict:
    """
    Check if a phone number's SIM card was recently swapped.
    Critical fraud prevention signal — SIM swaps often precede account takeovers.
    Use before high-value B2C disbursements to verify recipient identity is stable.
    Returns swap status and last swap date.
    """
    phone = _normalize_phone(phone)
    token = _get_mpesa_token()
    resp = requests.post(
        f"{_mpesa_base()}/v1/sim-swap/status",
        json={"MobileNumber": phone},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "phone": phone,
        "swap_detected": data.get("SimSwapStatus") == "SWAPPED",
        "last_swap_date": data.get("LastSwapDate"),
        "risk_level": "HIGH" if data.get("SimSwapStatus") == "SWAPPED" else "LOW",
        "recommendation": "Verify identity via alternative channel before disbursing" if data.get("SimSwapStatus") == "SWAPPED" else "SIM stable — proceed normally",
        "raw": data,
    }


@mcp.tool(description="Verify a Safaricom number: registration date, SIM age, last swap date and a hashed IMSI, with risk indicators (recently swapped; SIM age below 30 as returned by the API). Use for identity or fraud checks before onboarding or paying. This queries personal data about a subscriber: do so only with a lawful basis and any consent required under the Data Protection Act 2019. Returns those fields and the risk indicators. Read-only.", annotations={"title": "IMSI Query — Phone Verification", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
def mpesa_imsi_query(
    phone: Annotated[str, "Phone number to verify"],
) -> dict:
    """
    Verify a Safaricom number — returns registration date, SIM age, last swap, and hashed IMSI.
    Enhanced KYC/AML signal for financial services compliance.
    Older SIMs with no recent swaps have lower fraud risk.
    Returns data suitable for risk scoring without exposing raw IMSI.
    """
    phone = _normalize_phone(phone)
    token = _get_mpesa_token()
    resp = requests.post(
        f"{_mpesa_base()}/v1/sim-swap/query",
        json={"MobileNumber": phone},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "phone": phone,
        "registration_date": data.get("RegistrationDate"),
        "sim_age_days": data.get("SimAge"),
        "last_swap_date": data.get("LastSwapDate"),
        "hashed_imsi": data.get("HashedIMSI"),
        "risk_indicators": {
            "recently_swapped": bool(data.get("LastSwapDate")),
            "young_sim": (int(data.get("SimAge", 9999)) < 30),
        },
    }


# ── AFRICA'S TALKING ─────────────────────────────────────────────────────────

@mcp.tool(description="Send an SMS to up to 1,000 recipients through Africa's Talking. Use only when the user has explicitly approved this exact message and recipient list. SENDS TO REAL PEOPLE: in live mode it needs confirm_send=true and refuses more recipients than the per-call cap (MPESA_MAX_SMS_RECIPIENTS, default 50); the sandbox is never restricted. Returns the number sent and failed, any failures, a summary and per-recipient status, cost and id, or a refusal saying what is missing. Sending cannot be undone.", annotations={"title": "Send SMS", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
def sms_send(
    message: Annotated[str, "SMS message text. Unicode supported (Kiswahili etc.)"],
    recipients: Annotated[list[str], "Phone numbers in E.164 format e.g. ['+254712345678']"],
    sender_id: Annotated[str, "Optional pre-registered alphanumeric sender ID"] = "",
    confirm_send: Annotated[bool, "Required in live mode: set true ONLY after the user has explicitly approved sending this exact message to these recipients."] = False,
) -> dict:
    """
    Send SMS to 1-1000 recipients via Africa's Talking.
    Works across Kenya, Nigeria, Ghana, Tanzania, Uganda, Rwanda and 15+ more.
    Returns per-recipient status and cost breakdown.
    """
    blocked = _guard_sms(recipients, confirm_send)
    if blocked:
        return blocked
    _at_init()
    sms = africastalking.SMS
    kwargs: dict = {"message": message, "recipients": recipients}
    if sender_id:
        kwargs["sender_id"] = sender_id
    response = sms.send(**kwargs)
    data = response["SMSMessageData"]
    results = data["Recipients"]
    success_count = sum(1 for r in results if r["status"] == "Success")
    return {
        "sent": success_count,
        "failed": len(results) - success_count,
        "failures": [{"number": r["number"], "status": r["status"]} for r in results if r["status"] != "Success"],
        "summary": data.get("Message", ""),
        "results": [{"number": r["number"], "status": r["status"], "cost": r.get("cost"), "id": r.get("messageId")} for r in results],
    }


# E.164 country prefix -> ISO currency. Used to catch the silent-wrong-amount
# failure: an agent topping up a +255 (TZS) number while currency_code is left at
# the KES default would previously send the wrong denomination with no error.
_COUNTRY_CURRENCY = {
    "254": "KES", "255": "TZS", "256": "UGX", "250": "RWF", "257": "BIF",
    "234": "NGN", "233": "GHS", "27": "ZAR", "251": "ETB", "265": "MWK",
    "260": "ZMW", "225": "XOF", "237": "XAF",
}


def _expected_currency(phone: str) -> str | None:
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    for length in (3, 2):
        if digits[:length] in _COUNTRY_CURRENCY:
            return _COUNTRY_CURRENCY[digits[:length]]
    return None


@mcp.tool(description="Send airtime to a phone (Safaricom, Airtel, MTN, Vodafone and others) in a currency. Use only when the user has explicitly approved this exact top-up. MOVES MONEY: in live mode it needs confirm_send=true and refuses amounts above the per-transaction cap (MPESA_MAX_AMOUNT_KES, default KES 100,000); the sandbox is never restricted. Returns the Africa's Talking response or a refusal saying what is missing.", annotations={"title": "Send Airtime", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
def airtime_send(
    phone: Annotated[str, "Recipient phone in E.164 format e.g. '+254712345678'"],
    amount: Annotated[str, "Amount as string e.g. '50'. Denominated in currency_code, NOT always KES."],
    currency_code: Annotated[str, "ISO currency: KES, TZS, UGX, RWF, NGN, GHS, ZAR, ETB, MWK, ZMW. MUST match the recipient's country — a mismatch is rejected, not silently sent."] = "KES",
    confirm_send: Annotated[bool, "Required in live mode: set true ONLY after the user has explicitly approved this exact payment (recipient and amount). Ignored in sandbox."] = False,
) -> dict:
    """
    Send airtime top-up to MTN/Safaricom/Airtel/Vodafone subscribers.
    Use for NGO field incentives, survey rewards, agent payouts.

    Currency is validated against the recipient's country code. Sending a KES
    amount to a Tanzanian number is rejected with the correct currency named,
    rather than topping up the wrong denomination silently.

    No real airtime sent in sandbox mode (AT_USERNAME=sandbox).
    """
    blocked = _guard("airtime_send", amount, confirm_send)
    if blocked:
        return blocked
    expected = _expected_currency(phone)
    if expected and currency_code.upper() != expected:
        return {
            "success": False,
            "error": (f"Currency mismatch: {phone} is a {expected} country but "
                      f"currency_code='{currency_code}'. Pass currency_code='{expected}' "
                      f"with the amount denominated in {expected}. No airtime was sent."),
            "expected_currency": expected,
            "provided_currency": currency_code.upper(),
        }
    _at_init()
    at = africastalking.Airtime
    response = at.send(phone_number=phone, amount=amount, currency_code=currency_code)
    recipients = response.get("responses", [])
    if recipients:
        r = recipients[0]
        return {"success": r.get("status") == "Success", "status": r.get("status"), "amount": r.get("amount"), "request_id": r.get("requestId"), "error": r.get("errorMessage") if r.get("status") != "Success" else None}
    return {"success": False, "error": "No response from API", "raw": response}


# ── Entry point ───────────────────────────────────────────────────────────────


@mcp.tool(description="Returns neutral guidance on choosing a model for these tools; no model is recommended and no benchmark or pricing claims are made. Use when someone asks which model to pair with this server. Takes no arguments. Returns a null recommendation, guidance, a deprecation note and the tool count (23). Read-only.", annotations={"title": "Model Hint", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
def get_model_hint() -> dict:
    """
    Returns neutral guidance on choosing a model for these tools (no model is recommended).
    """
    return {
        "recommended_model": None,
        "guidance": (
            "This server does not recommend a specific model and makes no benchmark or pricing claims. Use a model that follows tool schemas reliably, "
            "keep a person approving every money-moving or messaging call (confirm_send), and rehearse in the sandbox first."
        ),
        "deprecated": "Kept for compatibility. Earlier versions returned an unsourced model recommendation with benchmark scores and prices whose dates had passed.",
        "tools_count": 23,
    }

if __name__ == "__main__":
    mcp.run()

def main() -> None:
    """Console entry point."""
    mcp.run()
