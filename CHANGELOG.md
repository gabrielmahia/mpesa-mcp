# Changelog

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

