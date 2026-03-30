# mpesa-mcp

<!-- mcp-name: io.github.gabrielmahia/mpesa-mcp -->

> MCP server for East African fintech APIs — M-Pesa (Safaricom Daraja) and Africa's Talking

Give your AI agent the ability to trigger M-Pesa payments, check transaction status, send SMS, and top up airtime across 20+ African telecom networks.

[![Tests](https://github.com/gabrielmahia/mpesa-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/gabrielmahia/mpesa-mcp/actions)
[![PyPI](https://img.shields.io/pypi/v/mpesa-mcp)](https://pypi.org/project/mpesa-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Glama](https://glama.ai/mcp/servers/gabrielmahia/mpesa-mcp/badge)](https://glama.ai/mcp/servers/gabrielmahia/mpesa-mcp)

[![mpesa-mcp MCP server](https://glama.ai/mcp/servers/gabrielmahia/mpesa-mcp/badges/card.svg)](https://glama.ai/mcp/servers/gabrielmahia/mpesa-mcp)

## Why this exists

M-Pesa processes more transactions per day than PayPal does in Africa. Africa's Talking
reaches users in 20+ countries on basic phones via SMS and USSD. Neither has an MCP server.

This means every AI agent built today — Claude, GPT, Gemini, or any MCP-compatible runtime —
cannot trigger an M-Pesa payment or send a Kiswahili SMS without custom integration work.

`mpesa-mcp` closes that gap in one `pip install`.

## Tools

| Tool | Description |
|---|---|
| `mpesa_stk_push` | Trigger STK Push payment prompt on customer's M-Pesa phone |
| `mpesa_stk_query` | Check status of an STK Push request |
| `mpesa_transaction_status` | Query any M-Pesa transaction by receipt number |
| `sms_send` | Send SMS to 1–1,000 recipients across African networks |
| `airtime_send` | Send airtime top-up to any subscriber (KES, NGN, GHS, UGX, etc.) |

## Coverage

- **M-Pesa:** Kenya (Safaricom Daraja v3) — STK Push, C2B, transaction status
- **SMS/Airtime:** Kenya, Nigeria, Ghana, Tanzania, Uganda, Rwanda, South Africa, and 15+ more via Africa's Talking

## Install

```bash
pip install mpesa-mcp
```

Or run directly with `uvx`:

```bash
uvx mpesa-mcp
```

## Configuration

Set these environment variables before starting the server:

```bash
# M-Pesa (Safaricom Daraja)
MPESA_CONSUMER_KEY=your_consumer_key
MPESA_CONSUMER_SECRET=your_consumer_secret
MPESA_SHORTCODE=174379               # sandbox test shortcode
MPESA_PASSKEY=your_passkey
MPESA_CALLBACK_URL=https://yourdomain.com/mpesa/callback
MPESA_SANDBOX=true                   # set false for production

# Africa's Talking
AT_USERNAME=sandbox                  # your AT username (sandbox for testing)
AT_API_KEY=your_at_api_key
```

### Sandbox credentials

**M-Pesa sandbox:** https://developer.safaricom.co.ke — create a free app to get test credentials.
- Test shortcode: `174379`
- Test passkey: `bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919`

**Africa's Talking sandbox:** https://account.africastalking.com — use `username=sandbox`, any API key.

## Usage with Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "mpesa": {
      "command": "uvx",
      "args": ["mpesa-mcp"],
      "env": {
        "MPESA_CONSUMER_KEY": "your_key",
        "MPESA_CONSUMER_SECRET": "your_secret",
        "MPESA_SHORTCODE": "174379",
        "MPESA_PASSKEY": "your_passkey",
        "MPESA_CALLBACK_URL": "https://yourdomain.com/mpesa/callback",
        "MPESA_SANDBOX": "true",
        "AT_USERNAME": "sandbox",
        "AT_API_KEY": "your_at_key"
      }
    }
  }
}
```

## Usage with Claude Code

```bash
claude mcp add mpesa -- uvx mpesa-mcp
```

Set env vars in your shell before running `claude`.

## Example prompts

Once connected, you can ask your AI agent:

> "Send KES 500 STK Push to +254712345678 for order #1234"

> "Check if the payment QKL8ABC123 has been received"

> "Send an SMS to these 50 farmers with today's maize price: [list]"

> "Top up KES 50 airtime for our field agents: [list of numbers]"

## Real-world scenarios

**Field agent payment dispatch**
> "Send KES 300 STK Push to each of these 12 field agents for today's data collection: [list]"

The agent triggers 12 sequential STK pushes, tracks each `checkout_request_id`, and
polls for confirmation — without any code from you.

**Farmer alert + airtime**
> "SMS these 200 Garissa farmers that the river is rising. Then top up KES 20 airtime each so they can call in reports."

One prompt → 200 SMS messages and 200 airtime top-ups across Safaricom, Airtel, and Telkom.

**Payment reconciliation**
> "Check whether receipt OKL8M3B2HF was a successful payment and how much it was for"

Useful for support agents using Claude to verify M-Pesa transactions in real time.

## Tool annotations

All tools declare [MCP tool annotations](https://spec.modelcontextprotocol.io/specification/2025-03-26/server/tools/#tool-annotations) so clients can gate calls appropriately:

| Tool | readOnly | destructive | idempotent |
|------|----------|-------------|------------|
| `mpesa_stk_push` | ❌ | ✅ | ❌ |
| `mpesa_stk_query` | ✅ | ❌ | ✅ |
| `mpesa_transaction_status` | ✅ | ❌ | ✅ |
| `sms_send` | ❌ | ✅ | ❌ |
| `airtime_send` | ❌ | ✅ | ❌ |

Claude Desktop and other MCP clients will request confirmation before triggering payment, SMS, or airtime operations.

## Server discovery

Capabilities are advertised via [`.well-known/mcp.json`](.well-known/mcp.json) — the emerging MCP Server Cards standard. Registries and browsers can index this server's tools without connecting to it.

```bash
# Check capabilities
curl https://raw.githubusercontent.com/gabrielmahia/mpesa-mcp/main/.well-known/mcp.json
```

## Testing and accuracy

The MCP ecosystem benchmark (CData, 2026) found most MCP servers accurate 60–75% of the time on complex queries — particularly silent failures on write operations and partial parameter application.

mpesa-mcp is tested against all three Kenyan phone number formats, boundary amount values, and missing optional fields:

```bash
pytest tests/ -v  # run full suite
pytest tests/test_phone_formats.py  # format normalization
pytest tests/test_boundary_amounts.py  # min/max amount edge cases
```

Write operations (STK push, SMS, airtime) have explicit validation before any API call is made.


## MCP vs A2A — two different protocols

mpesa-mcp implements **MCP** (Model Context Protocol) — how an AI agent talks to tools.

There is a complementary protocol, **A2A** (Agent-to-Agent), which handles how agents
talk to *each other*. They solve different problems and work together:

- **MCP**: Your AI agent → mpesa-mcp → Daraja API / Africa's Talking
- **A2A**: Orchestrator agent ↔ payment sub-agent ↔ notification sub-agent

For most integrations you only need MCP. A2A becomes relevant when you're building
multi-agent systems where a payment workflow coordinates with other specialized agents.

---
## Development

```bash
git clone https://github.com/gabrielmahia/mpesa-mcp
cd mpesa-mcp
pip install -e ".[dev]"
pytest tests/ -v
```

## Security

Do not commit API keys. Use environment variables or a secrets manager.  
Report vulnerabilities to: contact@aikungfu.dev

## License

[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) — © 2026 Gabriel Mahia