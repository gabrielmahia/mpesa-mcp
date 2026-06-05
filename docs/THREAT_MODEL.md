# Threat Model — mpesa-mcp

Framework: STRIDE + OWASP MCP Top 10 (2025) + MCP-38 Taxonomy (arXiv:2603.18063)

---

## System Description

mpesa-mcp is a Model Context Protocol server that proxies the Safaricom Daraja API and Africa's Talking API. It is a stateless, stdio-transport server that:
1. Receives tool call requests from an MCP client (Claude, etc.)
2. Validates inputs
3. Makes HTTPS calls to Daraja/AT APIs using operator-supplied credentials
4. Returns structured JSON responses

**Trust boundary:** Between the MCP client and this server. The server trusts that the MCP client is legitimate and that operator-configured credentials are authorized.

---

## Assets

| Asset | Sensitivity | Location |
|-------|-------------|----------|
| MPESA_CONSUMER_KEY/SECRET | High | Environment variable (never logged) |
| MPESA_PASSKEY | High | Environment variable |
| MPESA_INITIATOR_NAME | Medium | Environment variable |
| MPESA_SECURITY_CREDENTIAL | High | Environment variable |
| AT_API_KEY | High | Environment variable |
| Daraja OAuth token | High | In-memory cache only (expires 1h) |
| Phone numbers (in transit) | Medium | Hashed before logging |
| Transaction receipts | Medium | Returned to MCP client, not stored |

---

## Threats

### T1: Prompt Injection via Tool Parameters (OWASP MCP02, LLM01)
**Threat:** An attacker crafts a malicious string in a tool parameter (e.g., account_ref, remarks) that causes unintended behavior.
**Likelihood:** Low. Daraja API treats all fields as data, not instructions.
**Mitigations:** String fields are validated for length (max 12-100 chars). No shell command or SQL interpolation. Daraja API has its own input sanitization.
**Residual risk:** Accepted.

### T2: Credential Exfiltration via Log Injection (OWASP MCP01, MCP06)
**Threat:** Attacker injects log-readable content through tool parameters to exfiltrate credentials.
**Likelihood:** Very Low. `_audit()` only logs tool name, sanitized params (PII hashed), and outcome. Credentials are never logged.
**Mitigations:** Explicit exclusion of all credential env vars from audit logs. PII hashing (SHA-256) of phone numbers.
**Residual risk:** Accepted.

### T3: Unauthorized Financial Transactions (OWASP MCP03)
**Threat:** An attacker tricks the MCP client into calling mpesa_b2c or mpesa_stk_push with attacker-controlled parameters.
**Likelihood:** Medium (depends on MCP client security).
**Mitigations:** `destructiveHint: true` on all payment tools — MCP clients show confirmation dialogs. Amount bounds enforced (KES 1–150,000). Initiator credentials required for B2C (separate from STK Push credentials). Sandbox mode blocks real transactions.
**Residual risk:** Moderate — operators must configure their MCP client correctly.

### T4: Fake SIM Swap Results (OWASP MCP07)
**Threat:** A rogue MCP server replaces mpesa-mcp and returns false "no swap" results to enable fraud.
**Likelihood:** Low (requires server substitution).
**Mitigations:** Server is versioned and signed (PyPI trusted publisher). Documentation advises verifying installed package version. Glama registry validates server integrity.
**Residual risk:** Low.

### T5: Denial of Service via Tool Flooding (OWASP MCP10)
**Threat:** An MCP client calls tools in rapid succession, exhausting Daraja API rate limits.
**Likelihood:** Low (depends on operator setup).
**Mitigations:** Explicit timeouts on all API calls (10-30s). Daraja API rate-limits by shortcode. No unbounded loops or recursion.
**Residual risk:** Low — operators should implement client-side rate limiting.

### T6: Tool Description Poisoning (arXiv:2603.18063, MCP-38)
**Threat:** A modified version of mpesa-mcp has altered tool descriptions to cause unsafe agent behavior.
**Likelihood:** Very Low (requires supply chain attack).
**Mitigations:** PyPI Trusted Publisher (OIDC) — only GitHub Actions with specific workflow can publish. All releases signed. Users should verify package integrity: `pip install mpesa-mcp==VERSION --hash ...`
**Residual risk:** Very Low.

---

## Out of Scope

- Security of the Safaricom Daraja API itself
- Security of Africa's Talking API itself  
- Security of the MCP client (Claude, Claude Code, etc.)
- Network-level attacks between MCP client and server (stdio transport is local)
- Social engineering of operators to disclose credentials

---

## Residual Risks Accepted

All residual risks above are accepted by design. The highest-risk scenario (T3) requires an MCP client that bypasses tool confirmations — operators should verify their MCP client implements `destructiveHint` handling correctly.

---

*Threat model version: 1.0 | June 2026*
*Framework: STRIDE | OWASP MCP Top 10 2025 | arXiv:2603.18063*
