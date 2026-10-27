"""Human confirmation for the money-out tools, through MCP elicitation.

`confirm_send` is a parameter the same model supplies, so it is not an independent check. This middleware asks the HUMAN, through the client, to approve the exact payment before
a guarded tool runs, and sets `confirm_send` itself only after they say yes. It works in both protocol eras:

* MCP 2026-07-28 (multi-round trip): the first leg returns an "input required" result; the client asks the person and re-sends the call with the answer. The approval is BOUND to the
  exact call (a digest of the tool and its arguments is carried in the sealed request state), SINGLE-USE (a nonce is consumed) and SHORT-LIVED, so an agent cannot reuse one tap for a
  different payment or for repeated payments.
* Older eras: `Context.elicit` asks inside the same call.

MPESA_CONFIRM_MODE: `auto` (default: ask when the client can answer, otherwise fall back to the `confirm_send` parameter), `elicit` (strict: refuse when the client cannot answer) or
`param` (the old behaviour: the parameter only). The sandbox, and MPESA_REQUIRE_CONFIRMATION=false, are never prompted.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import time
from collections import OrderedDict

import mcp.types as mt
from fastmcp.server.elicitation import AcceptedElicitation
from fastmcp.server.middleware import Middleware
from fastmcp.tools.base import InputRequiredToolResult, ToolResult

# Every tool that calls the guard, and the parameter that names who is paid (None: no free recipient). A test pins this set to the source.
GUARDED = {"mpesa_b2c": "phone", "mpesa_business_paybill": "receiver_paybill", "mpesa_business_buygoods": "till_number", "mpesa_business_pochi": "phone",
           "mpesa_b2b_express_checkout": "receiver_till", "airtime_send": "phone", "mpesa_reversal": None, "mpesa_tax_remittance": None}
CONFIRM_KEY = "mpesa_confirm"
APPROVAL_TTL_SECONDS = 300
_REFERENCE_PARAMS = ("account_reference", "remarks", "occasion", "transaction_id")
_consumed: OrderedDict = OrderedDict()
_consumed_lock = threading.Lock()


def confirm_mode() -> str:
    raw = os.environ.get("MPESA_CONFIRM_MODE", "auto").strip().lower()
    return raw if raw in ("auto", "elicit", "param") else "auto"


def _digest(tool: str, args: dict) -> str:
    """A digest of the call the human is approving: the tool and every argument except confirm_send."""
    body = {k: v for k, v in sorted((args or {}).items()) if k != "confirm_send"}
    return hashlib.sha256(json.dumps({"tool": tool, "args": body}, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def make_state(tool: str, args: dict, now: float | None = None) -> str:
    return f"{_digest(tool, args)}.{secrets.token_hex(8)}.{int(now if now is not None else time.time())}"


def state_is_valid_and_consume(state, tool: str, args: dict, now: float | None = None) -> bool:
    """True only if the state belongs to THIS exact call, is not expired, and has not been used before. A valid state is consumed, so it works once."""
    try:
        digest, nonce, ts = str(state).split(".")
        age = (now if now is not None else time.time()) - int(ts)
    except ValueError:
        return False
    if digest != _digest(tool, args) or age < 0 or age > APPROVAL_TTL_SECONDS:
        return False
    with _consumed_lock:
        if nonce in _consumed:
            return False
        _consumed[nonce] = True
        while len(_consumed) > 1000:
            _consumed.popitem(last=False)
    return True


def describe(tool: str, args: dict) -> str:
    """What the person is shown. The recipient is shown in full: the person approving is the operator, and masking would defeat the check."""
    from . import server as s
    param = GUARDED[tool]
    lines = ["Approve this payment from your M-PESA account?", "", f"Tool: {tool}"]
    if param and args.get(param) is not None:
        given, norm = str(args[param]), s._normalize_recipient(args[param])
        lines.append(f"Pay to: {given}" + (f" (= {norm})" if norm != given else ""))
    try:
        lines.append(f"Amount: KES {float(args.get('amount')):,.0f}")
    except (TypeError, ValueError):
        lines.append(f"Amount: {args.get('amount')}")
    for k in _REFERENCE_PARAMS:
        if args.get(k) not in (None, ""):
            lines.append(f"{k.replace('_', ' ').capitalize()}: {args[k]}")
    budget = s._session_budget()
    if budget:
        try:
            lines.append(f"Session budget left after this: KES {max(budget - s._spent_kes - float(args.get('amount')), 0):,.0f}")
        except (TypeError, ValueError):
            pass
    lines += ["", "Approve only if you asked for exactly this payment."]
    return "\n".join(lines)


def _result(refusal: dict) -> ToolResult:
    return ToolResult(structured_content=refusal)


def _client_can_confirm(ctx) -> bool:
    try:
        return bool(ctx.session.check_client_capability(mt.ClientCapabilities(elicitation=mt.ElicitationCapability())))
    except Exception:  # noqa: BLE001  any failure to learn the capability means we cannot rely on a prompt
        return False


def _is_modern(ctx) -> bool:
    check = getattr(ctx, "_is_modern_protocol", None)   # private in FastMCP; a test exercises it with a real client so a change breaks loudly
    return bool(check()) if callable(check) else False


def _refuse(s, tool, args, param, code, message) -> ToolResult:
    s._audit(tool, {"amount": args.get("amount")}, code)
    s._record(tool, args.get("amount"), args.get(param) if param else None, code)
    return _result(s._refusal(code, message))


class HumanConfirmation(Middleware):
    async def on_call_tool(self, context, call_next):
        from . import server as s
        tool = context.message.name
        mode = confirm_mode()
        if tool not in GUARDED or mode == "param" or s._is_sandbox() or os.environ.get("MPESA_REQUIRE_CONFIRMATION", "true").lower() == "false":
            return await call_next(context)
        args = dict(context.message.arguments or {})
        param = GUARDED[tool]
        early = s._preflight(tool, args.get("amount"), args.get(param) if param else None)
        if early:   # refused anyway: do not ask the person to approve it
            return _refuse(s, tool, args, param, early[0], early[1]["error"])
        ctx = context.fastmcp_context
        if not _client_can_confirm(ctx):
            if mode == "elicit":
                return _refuse(s, tool, args, param, "BLOCKED_NO_CONFIRMATION_CHANNEL", "This server requires the person to confirm each payment through the client (MPESA_CONFIRM_MODE=elicit), and this client cannot show a confirmation prompt.")
            return await call_next(context)   # auto: fall back to the confirm_send parameter
        prompt = describe(tool, args)
        if _is_modern(ctx):
            response = (getattr(ctx, "input_responses", None) or {}).get(CONFIRM_KEY)
            if response is None or not state_is_valid_and_consume(getattr(ctx, "request_state", None), tool, args):
                schema = {"type": "object", "properties": {"approve": {"type": "boolean", "title": "Approve this payment", "description": "Tick to approve exactly this payment."}}, "required": ["approve"]}
                return InputRequiredToolResult(mt.InputRequiredResult(input_requests={CONFIRM_KEY: mt.ElicitRequest(params=mt.ElicitRequestFormParams(message=prompt, requested_schema=schema))}, request_state=make_state(tool, args)))
            approved = getattr(response, "action", None) == "accept" and bool((getattr(response, "content", None) or {}).get("approve"))
        else:
            answer = await ctx.elicit(prompt, response_type=bool)
            approved = isinstance(answer, AcceptedElicitation) and answer.data is True
        if not approved:
            return _refuse(s, tool, args, param, "BLOCKED_DECLINED_BY_HUMAN", "The person declined this payment. Do not retry; ask them what they want.")
        approved_message = context.message.model_copy(update={"arguments": {**args, "confirm_send": True}})
        return await call_next(context.copy(message=approved_message))
