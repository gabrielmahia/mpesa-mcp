# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in mpesa-mcp:

**DO NOT open a public issue.**

Email directly to: **contact@aikungfu.dev**

Response commitment: acknowledgement within 48 hours, triage within 7 days.
We follow coordinated disclosure — please allow 90 days before public disclosure.

---

## Security Framework Alignment

mpesa-mcp is designed in alignment with authoritative AI security guidance:

### NSA/CISA Joint Guidance
- **"Deploying AI Systems Securely"** (U/OO/143395-24, April 2024) — NSA AISC × CISA × FBI × ASD ACSC × CCCS × NCSC-UK × NCSC-NZ
- **"AI Data Security"** (U/OO/157249-25, May 2025) — NSA × CISA × FBI × ASD ACSC × NCSC-UK × NCSC-NZ
- **"Guidelines for Secure AI System Development"** (November 2023) — NSA AISC × NCSC-UK × CISA

### OWASP AI Security
- **OWASP MCP Top 10 (2025)** — https://owasp.org/www-project-mcp-top-10/
- **OWASP LLM Top 10 (2025)** — https://genai.owasp.org
- **OWASP MCP Security Cheat Sheet** — https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html

### Academic Research
- arXiv:2603.18063 — "MCP-38: A Comprehensive Threat Taxonomy for Model Context Protocol Systems" (2026)
- arXiv:2603.21642 — "Are AI-assisted Development Tools Immune to Prompt Injection?" (2026)

### Standards
- NIST AI Risk Management Framework (NIST AI 100-1)
- NIST AI 600-1: Generative AI Profile
- Kenya Data Protection Act 2019 (for data handling)

---

## Security Controls by OWASP MCP Top 10

### MCP01 — Token Mismanagement & Secret Exposure
**Mitigated.** All credentials are loaded exclusively from environment variables. No secrets in code, logs, or git history. API tokens are short-lived (OAuth 2.0 with 1-hour expiry, auto-refreshed). Token caching uses in-memory only (no disk persistence).

### MCP02 — Tool Poisoning & Prompt Injection
**Mitigated.** Tool descriptions are author-controlled and versioned in source. Inputs are structurally validated (type annotations, bounds checking) before any external API call. String parameters are not interpolated into shell commands or SQL. The server only calls well-defined external APIs with fixed schemas.

### MCP03 — Excessive Agency & Scope Creep
**Mitigated.** Each tool does exactly one thing. Tool annotations declare scope:
- `readOnlyHint: true` — read-only tools cannot modify state
- `destructiveHint: true` — write tools require explicit parameters
- `idempotentHint` — declared per tool
MCP clients (Claude Desktop, Claude Code) respect these annotations to gate confirmations.

### MCP04 — Insecure Transport & Authentication
**Mitigated.** All external API calls use HTTPS only. No fallback to HTTP. OAuth bearer tokens are passed via Authorization header only (never in URL query parameters).

### MCP05 — Supply Chain & Dependency Risk
**Mitigated.** All dependencies are locked in `pyproject.toml` with minimum version constraints. Dependency provenance: FastMCP (MIT), requests (Apache 2.0), africastalking (MIT). No dependencies from unknown publishers. GitHub Actions CI validates syntax on every push.

### MCP06 — Audit Trail & Logging Failures
**Mitigated.** All tool calls are logged via `_audit()` with structured output. PII (phone numbers, account identifiers) is SHA-256 hashed before writing to logs. Log entries include: TOOL name, sanitized PARAMS, OUTCOME. No raw credentials or full phone numbers in logs.

### MCP07 — Confused Deputy & Authorization Bypass
**Mitigated.** The server acts only on behalf of the operator who configured it. No user impersonation. No capability escalation. Tool inputs are validated to prevent parameter injection attacks (e.g., malformed shortcodes, out-of-bounds amounts).

### MCP08 — Context Injection & Over-Sharing
**Mitigated.** The server is stateless — no session state shared between tool calls. No persistent context storage. Each tool call is independent.

### MCP09 — Insecure Plugin/Server Composition
**Mitigated.** mpesa-mcp does not dynamically load external plugins or tools. All tool definitions are static and versioned.

### MCP10 — Denial of Service & Resource Exhaustion
**Partially mitigated.** All external API calls have explicit timeouts (10-30 seconds). No recursive or unbounded operations. Rate limiting is enforced by the upstream APIs (Safaricom Daraja, Africa's Talking). Operators should implement additional rate limiting at the MCP client level for production deployments.


### M-PESA Specific Controls

**Financial transaction security:**
- Amount bounds validation: STK Push limited to KES 1–150,000 per call
- Phone number normalization: E.164 format enforced before API call
- Sandbox/production isolation: `MPESA_SANDBOX` env var required; defaults to sandbox
- No real money in sandbox: Daraja sandbox processes no actual funds

**SIM Swap / Fraud Prevention (v0.2.0+):**
- `mpesa_sim_swap_query` and `mpesa_imsi_query` tools are read-only
- These tools call Safaricom's official fraud prevention APIs
- Results should be used as signals, not sole authorization decisions
- Operators are responsible for AML/KYC compliance in their jurisdiction

**B2C/B2B disbursement security:**
- Initiator credentials (`MPESA_INITIATOR_NAME`, `MPESA_SECURITY_CREDENTIAL`) required separately from core credentials
- This separation means accidental misconfiguration cannot enable unauthorized disbursements
- All disbursement tool calls are logged with PII-hashed recipient identifiers


---

## OWASP LLM Top 10 (2025) Alignment

| Risk | Status | Notes |
|------|--------|-------|
| LLM01: Prompt Injection | Mitigated | Inputs structurally validated; no free-text interpolation into API calls |
| LLM02: Insecure Output Handling | Mitigated | API responses returned as structured JSON; no eval/exec |
| LLM03: Training Data Poisoning | N/A | Not a training system |
| LLM04: Model DoS | Mitigated | Timeouts on all external calls |
| LLM05: Supply Chain | Mitigated | Pinned dependencies, MIT/Apache-2.0 only |
| LLM06: Sensitive Information Disclosure | Mitigated | PII hashed in logs; credentials in env vars |
| LLM07: Insecure Plugin Design | Mitigated | Tool annotations, strict input schemas |
| LLM08: Excessive Agency | Mitigated | Each tool scoped to single operation |
| LLM09: Overreliance | Addressed | README documents sandbox vs production distinction |
| LLM10: Model Theft | N/A | No model weights; uses external APIs |

---

## NSA/CISA Principle Alignment

Aligned with the **6 deployment security principles** from NSA/CISA "Deploying AI Systems Securely" (2024):

1. **Govern the AI deployment** — versioned releases (SemVer), changelog, documented threat model
2. **Understand the AI model and its operating environment** — README documents API dependencies, data flows, and sandbox vs production behavior
3. **Validate the AI system before deployment** — CI/CD lint + test gates on every push and tag
4. **Secure the AI system's infrastructure** — HTTPS only, no credentials in code, env-var-based configuration
5. **Secure the AI system at the application layer** — input validation, output structuring, no free-text injection surfaces
6. **Operationalize AI system security** — audit logging, vulnerability disclosure policy, coordinated disclosure commitment

Aligned with **CISA "AI Data Security"** (U/OO/157249-25, May 2025) data management principles:
- Data integrity: no mutation of external data sources; read-only tools do not modify state
- Data provenance: NDMA/Safaricom/AT data sources documented with official URLs
- Data minimization: only required fields transmitted to external APIs

---

## Responsible Disclosure History

No security vulnerabilities reported to date.

---

## Scope

This security policy covers the mpesa-mcp source code and its official PyPI release.
It does not cover:
- The Safaricom Daraja API or Africa's Talking API (report to their respective security teams)
- MCP clients (Claude, etc.) — report to their respective security contacts
- Third-party deployments or forks of mpesa-mcp

---

*© 2026 Gabriel Mahia / AI Kung Fu LLC. MIT License.*
*Security policy last updated: June 2026*
*Framework references: NSA/CISA U/OO/143395-24, U/OO/157249-25 | OWASP MCP Top 10 2025 | OWASP LLM Top 10 2025*
