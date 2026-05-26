## [0.1.9] — 2026-05-25

### Security
- NSA CSI U/OO/6030316-26 compliance: structured audit logging, KE phone validation, amount bounds
- First African MCP server to document NSA MCP security framework alignment

### Changed
- Audit logs hash phone numbers (SHA-256) before writing — no PII in logs
- Amount validation: [1, 150,000 KES] enforced before Daraja API call
- Error containment: all handlers return structured dicts, no raw exceptions

### Infrastructure
- GitHub Actions CI/CD: publish to PyPI on git tag v* push (PYPI_UPDATED secret)
- NSA compliance badge added to README


## [0.1.8] — 2026-04-26

### Fixed
- PyPI now shows `License: MIT` correctly (the OSI classifier added in 0.1.7 source
  required a new wheel build to take effect on pypi.org)

## [0.1.7] — 2026-04-23

### Changed
- **License changed to MIT** — mpesa-mcp and all MCP/SDK infrastructure repos now use MIT
  for maximum ecosystem compatibility. Streamlit apps remain CC BY-NC-ND 4.0.
- Updated `glama.json` with `maintainers`, `version`, and `envVars` fields for Glama claim
- Added `NOTICE` file with attribution and third-party library notices
- Related servers: `wapimaji-mcp` (Kenya drought intelligence MCP)

## [0.1.6] — 2026-04-06

### Fixed
- Added `license-files = ["LICENSE"]` to pyproject.toml so PyPI correctly displays CC-BY-NC-ND-4.0
- Added newsletter subscription link to README

### Changed
- No code changes from 0.1.5

## [0.1.4] — 2026-03-30

### Changed
- Version bump only — resolves PyPI filename collision from partial 0.1.3 upload
- No code changes from 0.1.3

# Changelog

## [0.1.9] — Security Hardening (NSA-CSI-2026)

### Security
- Added structured audit logging for all M-Pesa tool invocations (NSA CSI U/OO/6030316-26 compliance)
- Added Kenyan phone number validation regex (`^254[17]\d8$`) — rejects malformed inputs before API calls
- Added M-Pesa amount bounds validation [1–150,000 KES] — Safaricom STK push hard limits
- PII fields (phone numbers) SHA-256 hashed in audit logs — prevents log-based data leakage
- Error containment: validation failures return structured `{"error": "..."}` dicts instead of raw exceptions
- References: NSA CSI U/OO/6030316-26 (May 2026), OWASP A08:2017

## [0.1.3] — 2026-03-30

### Added
- MCP tool annotations on all 5 tools per spec 2025-03-26:
  - `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`
  - Claude Desktop and compatible clients now show confirmation dialogs before
    payment, SMS, and airtime operations
- `.well-known/mcp.json` for MCP Server Cards discovery (roadmap priority)
  - Registries and browsers can index capabilities without connecting
- README: tool annotations table, .well-known section, accuracy/testing notes

### Changed
- All tool decorators updated to include annotations dict

