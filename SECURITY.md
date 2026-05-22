# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅         |
| < 0.1   | ❌         |

## Security Design Alignment

mpesa-mcp is designed in alignment with:
- **NSA CSI U/OO/6030316-26 (May 2026)** — Model Context Protocol: Security Design Considerations
- **OWASP A08:2017** — Insecure Deserialization (mitigated via strict JSON schema validation)
- **Safaricom Daraja API security guidelines** (HTTPS-only, token rotation, sandbox isolation)
- **Kenya CBK data governance requirements** (audit trails for financial transactions)

### NSA MCP Security Controls — Implementation Status

| NSA Recommendation | Status | Implementation |
|---|---|---|
| Access control / authentication | ✅ | Environment-variable credentials only; no hardcoded secrets |
| Parameter validation | ✅ | KE phone regex (`^254[17]\d{8}$`), amount bounds [1–150,000 KES] |
| Audit logging | ✅ | Structured log entry per tool invocation; PII fields SHA-256 hashed |
| Token lifecycle | ✅ | OAuth token cached with expiry; auto-refreshed before each request |
| Sandbox / production isolation | ✅ | `MPESA_SANDBOX=true/false`; separate Daraja base URLs enforced |
| HTTPS enforcement | ✅ | All Daraja and AT API calls use `https://`; no HTTP fallback |
| Error containment | ✅ | Tool handlers return structured error dicts; no raw exception propagation |
| No hardcoded secrets | ✅ | All credentials via environment variables |
| Input injection prevention | ✅ | Phone and amount fields validated before any network call |

### Known limitations (per NSA guidance)

- MCP protocol-level session authentication is not enforced by the spec;
  this server relies on transport TLS + environment isolation (standard for current MCP ecosystem)
- Audit logs written to stdout — operators should pipe to a SIEM or log aggregator in production
- Distributed deployments should use a shared token store for cross-instance token replay protection

## Reporting a Vulnerability

If you discover an error:

DO NOT open a public issue.

Email directly to:
contact@aikungfu.dev
