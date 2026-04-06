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

