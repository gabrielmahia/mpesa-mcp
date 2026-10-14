# Changelog — mpesa-mcp

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
