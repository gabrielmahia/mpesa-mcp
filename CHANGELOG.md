# Changelog — mpesa-mcp

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
