# AGENTS.md — mpesa-mcp

This file gives AI coding agents (Cursor, GitHub Copilot, Claude Code, Devin, etc.)
the context needed to work reliably in this repository.

## What this repo is

An MCP server that gives AI agents access to:
- **M-Pesa Daraja API** — STK Push payments, transaction status queries
- **Africa's Talking** — SMS to 20+ African telecom networks, airtime top-up

All tools handle real financial operations. Test in **sandbox mode only**.

## Architecture

```
src/mpesa_mcp/
  server.py     ← All tool definitions and MCP server entry point
  __init__.py   ← Package version
tests/
  test_smoke.py ← Basic import and tool registration tests
.well-known/
  mcp.json      ← MCP Server Cards discovery metadata
```

Single-file architecture — all tools are in `server.py`. The server uses FastMCP.

## Tool annotations (critical)

All 5 tools declare MCP `ToolAnnotations`. **Do not remove or change these** without understanding the implications:

- `readOnlyHint: True` on query tools — clients auto-approve these
- `destructiveHint: True` on write tools — clients show confirmation dialogs
- Removing `destructiveHint: True` from payment/SMS tools is a **safety issue**

## Environment variables

```bash
# M-Pesa (Daraja)
MPESA_CONSUMER_KEY=
MPESA_CONSUMER_SECRET=
MPESA_SHORTCODE=174379          # sandbox default
MPESA_PASSKEY=                  # from Daraja portal
MPESA_CALLBACK_URL=             # must be public HTTPS
MPESA_ENVIRONMENT=sandbox       # or: production

# Africa's Talking
AT_API_KEY=
AT_USERNAME=sandbox             # or: your production username
```

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Phone number handling

M-Pesa accepts Kenyan numbers in multiple formats. The server normalizes all to `254XXXXXXXXX`:
- `0712345678` → `254712345678`
- `+254712345678` → `254712345678`
- `254712345678` → unchanged

**Do not bypass this normalization** — Daraja rejects other formats silently.

## Testing

Always test against Daraja **sandbox** (default). Sandbox STK Push sends a simulated prompt
to the phone — no real money moves.

```bash
MPESA_ENVIRONMENT=sandbox pytest tests/ -v
```

## Adding new tools

1. Define the function in `server.py` with `@mcp.tool(annotations={...})`
2. Set `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint` accurately
3. Add a smoke test in `tests/test_smoke.py`
4. Update `.well-known/mcp.json` tool list
5. Bump version in `pyproject.toml` and `server.json`

## License

CC-BY-NC-ND-4.0 — free to use with attribution, no commercial redistribution, no derivatives.
Contact `contact@aikungfu.dev` for exceptions.
