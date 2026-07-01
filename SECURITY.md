# Security Policy

## Reporting Vulnerabilities

This MCP server handles real financial and civic data for East African users.
If you discover a security vulnerability, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Report via: security@mngonline.dev  
Response time: within 72 hours.

---

## MCP Security Context (2026)

This server is built and maintained in awareness of the current MCP security landscape.
Key references applied during development:

- **OWASP MCP Top 10** (v0.1 Beta, 2025) — used as deployment checklist
- **MCPTox benchmark** (2025-2026): 45 live MCP servers tested; 66% had security findings.
  Claude-3.7-Sonnet / Sonnet 5 are the most resistant models in the study (<3% compliance
  with poisoned tool calls). This server is tested with those models.
- **mcp-scan** (uvx mcp-scan@latest): Run this against this server before production use.
- **Input validation**: All tool inputs are validated before passing to external APIs.
- **No secrets in tool descriptions**: Tool descriptions are audited to ensure no API keys,
  tokens, or internal paths appear in publicly visible metadata.

## Threat Model

| Threat | Mitigation |
|--------|-----------|
| Tool poisoning via description | Tool descriptions are minimal; audited before each release |
| Prompt injection via external data | External data is sanitized before inclusion in tool responses |
| Credential theft via logs | No credentials are logged; environment variable only |
| Supply chain attack | Dependencies pinned; SBOM available on request |
| Unauthorized tool execution | Tools are read-only where possible; write actions documented explicitly |

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest on PyPI | ✅ |
| Older than latest minor | ❌ Upgrade recommended |

## Security Scanning

Before connecting this server to a production agent pipeline:

```bash
# Run mcp-scan to verify tool descriptions are clean
uvx mcp-scan@latest

# Pin the package version — do not use latest tag in production
pip install mpesa-mcp==<pinned-version>
```

---

*This policy was last updated: July 2026.*  
*References: MCPTox benchmark (arXiv/ITECS 2026), OWASP MCP Top 10, mcp-scan.*
