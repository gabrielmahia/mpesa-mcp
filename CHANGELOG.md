# Changelog — mpesa-mcp

## 0.4.6
- **Allowed recipients:** `MPESA_ALLOWED_RECIPIENTS` (comma-separated phone numbers, paybills and tills) restricts the money-out tools to those recipients; anything else is refused and audited as `BLOCKED_RECIPIENT_NOT_ALLOWED`. Phone numbers match in any Kenyan format. Unset means no restriction (nothing changes for existing users). It applies to `mpesa_b2c`, `mpesa_business_paybill`, `mpesa_business_buygoods`, `mpesa_business_pochi`, `mpesa_b2b_express_checkout` and `airtime_send`; reversal and tax remittance have no free recipient.
- **New tool, `mpesa_session_report` (read-only; 24 tools):** the server's own record of the session: limits, spent and remaining, counts, and the last ten authorisations or refusals with recipients masked. It lets an operator or a model verify what was authorised without relying on a model's account of its own actions. Spending is now counted whenever a payment is authorised, even when the budget is opted out.
- **Honesty fixes in the documentation:** the README no longer calls the server "NSA MCP Guidance Compliant" (the NSA sheet is guidance, not a certifiable standard; the section is now a self-assessment, and a row that wrongly said no raw exception propagates is corrected); it no longer claims to "exceed" a third-party accuracy benchmark that was never measured; and the Swahili statistic that was misattributed to arXiv:2509.04516 is replaced by what that paper found. `SECURITY.md` now holds the required reporting block (it pointed to a different address and ranked models by resistance to poisoned tool calls, which this repository cannot support).
- Tests: 18 new (83 in all).

## 0.4.5
- **Security hardening:** a session budget bounds the TOTAL a server process may authorise in live mode (`MPESA_SESSION_BUDGET_KES`, default **300,000** KES; `0` or `none` = no budget, an explicit opt-out). Until now the 100,000 KES per-transaction cap bounded one payment but not the sum, so an agent could repeat a capped payment without limit. All eight money-out tools are covered through the single guard. It is counted when a payment is authorised and is not refunded on failure; a refusal is audited as `BLOCKED_OVER_SESSION_BUDGET` and tells the model not to retry. The sandbox is unaffected.
- **Behaviour change:** if you legitimately move more than 300,000 KES in one server session in live mode, set `MPESA_SESSION_BUDGET_KES` higher (or `0`).
- **Docs:** the README now says that `confirm_send` is supplied by the model, so the independent check is the MCP client's approval prompt, and recommends bounding the loss in the payment rail too (a dedicated low-balance shortcode, initiator limits).
- Tests: 9 new; the process-wide counter is reset around every test (`tests/conftest.py`), and one existing test that sends a very large amount now opts out of the budget explicitly. A test that could not fail was caught in review and replaced.

## 0.4.4
- **Fixed (audit):** every tool that logs `INITIATED` now also logs how the call ended, so the trail can be reconciled: `ACCEPTED`, `REJECTED:<code or status>`, `SENT:<n>/FAILED:<m>` (SMS), `RETURNED`, or `FAILED:<ExceptionType>` (the exception still propagates; only its type is logged, never its message). Refusals by the guard are still audited once as `BLOCKED_*`. A terminal line is written only if `INITIATED` was logged during that call.
- **Fixed (audit gap):** `sms_send` and `airtime_send` logged nothing when they succeeded; they now log `INITIATED` and a terminal line. SMS logs the number of recipients, never the numbers.
- **Fixed:** a missing credential now says which one (`MPESA_SHORTCODE is not set. Set it in the server's environment (see the README, Configuration).`) instead of a bare `KeyError: 'MPESA_SHORTCODE'`; 22 of the 23 tools used to fail that way without credentials.
- **Fixed:** the server reports its own version in the MCP handshake (it reported the FastMCP library version, 4.1.3).
- **Publishing:** the PyPI action is pinned to a commit, `mcp-publisher` is pinned to v1.8.1 with its SHA-256 verified, and the registry step is skipped when the version is already published, so a retry is harmless.
- Tests: 17 new (terminal outcomes, no numbers in the log, a blocked live-mode call never reaches the network, unchanged tool schema, every audited tool decorated, version agreement across pyproject, server.json, glama.json and the running server).

## 0.4.1
- Descriptions on PyPI, the registry and the MCP server card no longer claim the server was "tested with" a model; the README's Models section states that no model is recommended or certified.

## 0.4.0
- **Changed (live mode):** `sms_send` now needs `confirm_send=true` and refuses more than `MPESA_MAX_SMS_RECIPIENTS` recipients (default 50; 0 = no cap), like the money-moving tools. The sandbox is unrestricted.
- **Changed:** `get_model_hint()` returns neutral guidance; the unsourced benchmark scores and expired prices are gone.
- Real descriptions for all 23 tools, saying which move money or message people.

## v0.2.1 — 2026-07-01
- **Added** `get_model_hint()` tool (tool #23) — recommends `claude-sonnet-5` to
  Claude Desktop and Glama users connecting this server
- **Updated** README with Tested With section (Sonnet 5 + Opus 4.8)
- **Added** SECURITY.md — MCPTox 2026 threat model, OWASP MCP Top 10, mcp-scan guidance
- **Added** `.well-known/mcp-server-card.json` — MCP 2026 Server Card standard
- **Added** `DPGA_DATA_STATEMENT.md` — architecture statement for GID0093741 review

## v0.2.0 — 2026-06-15
- M-PESA Ratiba (standing orders) tools
- Bill Manager tools (opt-in, invoice, cancel)
- SIM swap and IMSI query tools
- STK Push, B2C, B2B, Dynamic QR, Tax Remittance
- Africa's Talking SMS + Airtime tools (sms_send, airtime_send)

## v0.1.x — 2025
- Initial Daraja API MCP implementation
- Core STK Push, account balance, transaction status
- PyPI publish via OIDC Trusted Publisher
