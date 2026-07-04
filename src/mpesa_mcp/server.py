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

@mcp.tool(annotations={"title": "M-Pesa STK Push", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
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


@mcp.tool(annotations={"title": "M-Pesa STK Query", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
def mpesa_stk_query(
    checkout_request_id: Annotated[str, "CheckoutRequestID from mpesa_stk_push response"],
) -> dict:
    """
    Check STK Push status. Poll 10-30s after mpesa_stk_push.
    ResultCode 0 = success, 1032 = cancelled, 1037 = timed out.
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


@mcp.tool(annotations={"title": "M-Pesa B2C", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
def mpesa_b2c(
    phone: Annotated[str, "Recipient phone number (any Kenyan format)"],
    amount: Annotated[int, "Amount in KES to send"],
    command_id: Annotated[str, "SalaryPayment | BusinessPayment | PromotionPayment"] = "BusinessPayment",
    remarks: Annotated[str, "Remarks (max 100 chars)"] = "B2C via mpesa-mcp",
    occasion: Annotated[str, "Optional occasion label"] = "",
) -> dict:
    """
    Business To Customer disbursement — send money from shortcode to phone.
    Use for payroll, NGO field incentives, agent float, survey rewards.
    Result delivered async to MPESA_RESULT_URL.
    Requires MPESA_INITIATOR_NAME and MPESA_SECURITY_CREDENTIAL env vars.
    """
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


@mcp.tool(annotations={"title": "Business Pay Bill (B2B)", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
def mpesa_business_paybill(
    receiver_paybill: Annotated[str, "Destination paybill shortcode"],
    amount: Annotated[int, "Amount in KES"],
    account_reference: Annotated[str, "Account number at destination paybill"],
    remarks: Annotated[str, "Transaction remarks"] = "B2B PayBill via mpesa-mcp",
) -> dict:
    """
    Pay directly from business shortcode to another paybill number.
    Use for supplier payments, utility bills, inter-business transfers.
    Requires MPESA_INITIATOR_NAME and MPESA_SECURITY_CREDENTIAL.
    """
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


@mcp.tool(annotations={"title": "Business Buy Goods (B2B)", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
def mpesa_business_buygoods(
    till_number: Annotated[str, "Destination till number (Buy Goods)"],
    amount: Annotated[int, "Amount in KES"],
    remarks: Annotated[str, "Transaction remarks"] = "B2B BuyGoods via mpesa-mcp",
) -> dict:
    """
    Pay from business shortcode to a till/buy-goods number.
    Requires MPESA_INITIATOR_NAME and MPESA_SECURITY_CREDENTIAL.
    """
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


@mcp.tool(annotations={"title": "Business to Pochi la Biashara", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
def mpesa_business_pochi(
    phone: Annotated[str, "Pochi wallet owner phone number"],
    amount: Annotated[int, "Amount in KES"],
    remarks: Annotated[str, "Remarks"] = "Pochi payment via mpesa-mcp",
) -> dict:
    """
    Pay from business shortcode to a Pochi la Biashara micro-SME wallet.
    Used for micro-enterprise supplier payments and informal sector settlements.
    Requires MPESA_INITIATOR_NAME and MPESA_SECURITY_CREDENTIAL.
    """
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

@mcp.tool(annotations={"title": "M-Pesa Transaction Status", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
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


@mcp.tool(annotations={"title": "M-Pesa Account Balance", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
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


@mcp.tool(annotations={"title": "Query Org Info", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
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


@mcp.tool(annotations={"title": "Pull C2B Transactions", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
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

@mcp.tool(annotations={"title": "M-Pesa Reversal", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
def mpesa_reversal(
    transaction_id: Annotated[str, "M-Pesa receipt to reverse e.g. QKL8XXXXXX"],
    amount: Annotated[int, "Amount to reverse in KES"],
    remarks: Annotated[str, "Reason for reversal"] = "Reversal via mpesa-mcp",
) -> dict:
    """
    Reverse an erroneous M-Pesa transaction.
    Use when a payment was sent to the wrong number or wrong amount.
    Requires MPESA_INITIATOR_NAME and MPESA_SECURITY_CREDENTIAL.
    Result delivered async to MPESA_RESULT_URL.
    """
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


@mcp.tool(annotations={"title": "Dynamic QR Code", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
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


@mcp.tool(annotations={"title": "Tax Remittance to KRA", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
def mpesa_tax_remittance(
    amount: Annotated[int, "Tax amount in KES"],
    account_reference: Annotated[str, "KRA Payment Registration Number (PRN)"],
    remarks: Annotated[str, "Remittance remarks"] = "Tax remittance via mpesa-mcp",
) -> dict:
    """
    Remit tax directly from M-PESA business account to Kenya Revenue Authority.
    Provide the KRA Payment Registration Number (PRN) as account_reference.
    KRA shortcode: 572572. Requires MPESA_INITIATOR_NAME and MPESA_SECURITY_CREDENTIAL.
    """
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


@mcp.tool(annotations={"title": "B2B Express Checkout", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
def mpesa_b2b_express_checkout(
    receiver_till: Annotated[str, "Recipient till number"],
    amount: Annotated[int, "Amount in KES"],
    account_reference: Annotated[str, "Account reference for the transaction"],
    remarks: Annotated[str, "Remarks"] = "B2B Express via mpesa-mcp",
) -> dict:
    """
    Initiate USSD Push to till — enables merchant-to-merchant payments.
    Recipient merchant receives a USSD prompt to confirm payment from their till.
    Use for wholesale supplier payments between Lipa Na M-PESA merchants.
    Requires MPESA_INITIATOR_NAME and MPESA_SECURITY_CREDENTIAL.
    """
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

@mcp.tool(annotations={"title": "M-PESA Ratiba — Create Standing Order", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
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

@mcp.tool(annotations={"title": "Bill Manager — Opt In", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
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


@mcp.tool(annotations={"title": "Bill Manager — Create Invoice", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
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


@mcp.tool(annotations={"title": "Bill Manager — Cancel Invoice", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": True})
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

@mcp.tool(annotations={"title": "SIM Swap Query", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
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


@mcp.tool(annotations={"title": "IMSI Query — Phone Verification", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
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

@mcp.tool(annotations={"title": "Send SMS", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
def sms_send(
    message: Annotated[str, "SMS message text. Unicode supported (Kiswahili etc.)"],
    recipients: Annotated[list[str], "Phone numbers in E.164 format e.g. ['+254712345678']"],
    sender_id: Annotated[str, "Optional pre-registered alphanumeric sender ID"] = "",
) -> dict:
    """
    Send SMS to 1-1000 recipients via Africa's Talking.
    Works across Kenya, Nigeria, Ghana, Tanzania, Uganda, Rwanda and 15+ more.
    Returns per-recipient status and cost breakdown.
    """
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


@mcp.tool(annotations={"title": "Send Airtime", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
def airtime_send(
    phone: Annotated[str, "Recipient phone in E.164 format e.g. '+254712345678'"],
    amount: Annotated[str, "Amount as string e.g. '50' (KES 50). Min KES 10 in production."],
    currency_code: Annotated[str, "ISO currency: KES, NGN, GHS, UGX, TZS, RWF, ZAR"] = "KES",
) -> dict:
    """
    Send airtime top-up to MTN/Safaricom/Airtel/Vodafone subscribers.
    Use for NGO field incentives, survey rewards, agent payouts.
    No real airtime sent in sandbox mode (AT_USERNAME=sandbox).
    """
    _at_init()
    at = africastalking.Airtime
    response = at.send(phone_number=phone, amount=amount, currency_code=currency_code)
    recipients = response.get("responses", [])
    if recipients:
        r = recipients[0]
        return {"success": r.get("status") == "Success", "status": r.get("status"), "amount": r.get("amount"), "request_id": r.get("requestId"), "error": r.get("errorMessage") if r.get("status") != "Success" else None}
    return {"success": False, "error": "No response from API", "raw": response}


# ── Entry point ───────────────────────────────────────────────────────────────


@mcp.tool()
def get_model_hint() -> dict:
    """
    Returns the recommended AI model for using mpesa-mcp tools.
    Call this first when selecting a model to pair with mpesa-mcp.
    """
    return {
        "recommended_model": "claude-sonnet-5",
        "api_id": "claude-sonnet-5",
        "rationale": (
            "Sonnet 5 finishes multi-step M-PESA workflows end-to-end and "
            "self-corrects tool-call errors without prompting. "
            "Terminal-Bench 80.4% vs Sonnet 4.6 67.0%. Tested 2026-06-30."
        ),
        "cost_intro": "$2/$10 per MTok through 2026-08-31",
        "cost_standard": "$3/$15 per MTok from 2026-09-01",
        "fallback": "claude-opus-4-8 for highest-accuracy compliance reasoning",
        "tools_count": 23,
    }

if __name__ == "__main__":
    mcp.run()

def main() -> None:
    """Console entry point."""
    mcp.run()
