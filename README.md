# mpesa-mcp

<!-- mcp-name: io.github.gabrielmahia/mpesa-mcp -->

> MCP server for East African fintech APIs — M-Pesa (Safaricom Daraja) and Africa's Talking

Give your AI agent the ability to trigger M-Pesa payments, check transaction status, send SMS, and top up airtime across 20+ African telecom networks.

[![Tests](https://github.com/gabrielmahia/mpesa-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/gabrielmahia/mpesa-mcp/actions)
[![PyPI](https://img.shields.io/pypi/v/mpesa-mcp)](https://pypi.org/project/mpesa-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Glama Score](https://glama.ai/mcp/servers/gabrielmahia/mpesa-mcp/badges/score.svg)](https://glama.ai/mcp/servers/gabrielmahia/mpesa-mcp)
[![smithery badge](https://smithery.ai/badge/@gabrielmahia/mpesa-mcp)](https://smithery.ai/server/@gabrielmahia/mpesa-mcp)
[![Glama](https://glama.ai/mcp/servers/gabrielmahia/mpesa-mcp/badge)](https://glama.ai/mcp/servers/gabrielmahia/mpesa-mcp)
[![NSA MCP Compliant](https://img.shields.io/badge/NSA%20CSI%20U%2FOO%2F6030316--26-MCP%20Security%20Compliant-blue)](https://www.nsa.gov/Portals/75/documents/Cybersecurity/CSI_MCP_SECURITY.pdf)

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


## Glama (hosted MCP)

mpesa-mcp is available as a hosted MCP server on [Glama](https://glama.ai/mcp/servers/gabrielmahia/mpesa-mcp):

[![mpesa-mcp MCP server](https://glama.ai/mcp/servers/gabrielmahia/mpesa-mcp/badges/card.svg)](https://glama.ai/mcp/servers/gabrielmahia/mpesa-mcp)
[![mpesa-mcp score](https://glama.ai/mcp/servers/gabrielmahia/mpesa-mcp/badges/score.svg)](https://glama.ai/mcp/servers/gabrielmahia/mpesa-mcp)



## Security — NSA MCP Guidance Compliant

`mpesa-mcp` was updated in response to **NSA CSI U/OO/6030316-26 (May 2026)** — the NSA Artificial Intelligence Security Center's Cybersecurity Information Sheet on Model Context Protocol security.

The implementation below documents compliance against the NSA's MCP security framework, control by control.

| NSA Control | Implementation |
|---|---|
| Parameter validation | KE phone regex `^254[17]\d{8}$` + amount bounds [1–150,000 KES] |
| Audit logging | Structured log per tool call; phone numbers SHA-256 hashed |
| Token lifecycle | OAuth token cached with expiry; auto-refreshed |
| Error containment | Structured error dicts; no raw exception propagation |
| HTTPS enforcement | All Daraja API calls HTTPS-only |
| No hardcoded secrets | All credentials via environment variables |

See [SECURITY.md](./SECURITY.md) for the full compliance table.

> **Reference:** [NSA CSI_MCP_SECURITY.pdf](https://www.nsa.gov/Portals/75/documents/Cybersecurity/CSI_MCP_SECURITY.pdf) — May 2026, UNCLASSIFIED

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


## Ecosystem context — Mojaloop + MCP

**Mojaloop** (funded by the Gates Foundation) handles payment *interoperability* — connecting banks, mobile money wallets, and merchants across DFSPs in East Africa and beyond.

**mpesa-mcp** handles the *AI agent tooling layer* — enabling AI coding assistants to trigger and query M-Pesa payments programmatically.

These are complementary:
- Mojaloop: the interoperability rails between financial providers
- mpesa-mcp: the MCP interface layer that connects AI agents to those rails

See the [Mojaloop documentation contribution](https://github.com/mojaloop/documentation/issues/553) for more on this pattern.

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


## Research Context

**MCP ecosystem benchmark** (CData, 2026): Most MCP servers achieve 60-75% accuracy on complex queries. mpesa-mcp includes explicit validation and bounds checking to exceed this baseline.

**Swahili AI accuracy** (arXiv:2509.04516, 2025): AI models produce 4× more errors in Swahili than English. mpesa-mcp's Swahili-native tool descriptions are designed to minimize this gap for Swahili-speaking users by eliminating the translation step in tool selection.

**MCP security research** (arXiv:2603.18063, arXiv:2603.21642, 2026): Prompt injection via tool descriptions is the primary MCP attack vector. mpesa-mcp mitigates this through static, versioned tool descriptions and strict input validation.

**Related infrastructure:**
- [wapimaji-mcp](https://github.com/gabrielmahia/wapimaji-mcp) — Kenya water/drought MCP
- [civic-agent-kit](https://github.com/gabrielmahia/civic-agent-kit) — Kenya civic data MCP
- [swahili-health-mcp](https://github.com/gabrielmahia/swahili-health-mcp) — Kenya DHIS2 health data MCP
- [kenya-legal-rag](https://github.com/gabrielmahia/kenya-legal-rag) — Kenya legal corpus MCP
- Full portfolio: [gabrielmahia.github.io](https://gabrielmahia.github.io)

## License

[MIT](https://creativecommons.org/licenses/by-nc-nd/4.0/) — © 2026 Gabriel Mahia


## Stay updated

Get notified of new releases and East African API developments:
**[Subscribe to updates →](https://buttondown.com/gabrielmahia)**

Or watch this repo on GitHub for release notifications.
## Sibling packages

| Package | Install | Description |
|---------|---------|-------------|
| [wapimaji-mcp](https://github.com/gabrielmahia/wapimaji-mcp) | `pip install wapimaji-mcp` | Kenya drought intelligence MCP server |
| [civic-agent-kit](https://github.com/gabrielmahia/civic-agent-kit) | `pip install civic-agent-kit` | East African civic AI SDK |
## Related packages

All MIT · All part of the East African civic AI stack

| Package | Install | Description |
|---------|---------|-------------|
| [wapimaji-mcp](https://github.com/gabrielmahia/wapimaji-mcp) | `pip install wapimaji-mcp` | Kenya drought intelligence MCP server |
| [kenya-health-mcp](https://github.com/gabrielmahia/kenya-health-mcp) | `pip install kenya-health-mcp` | Kenya health data MCP — NHIF, facilities, maternal, rights |
| [civic-agent-kit](https://github.com/gabrielmahia/civic-agent-kit) | `pip install civic-agent-kit` | East African civic AI SDK |

Full portfolio: [gabrielmahia.github.io](https://gabrielmahia.github.io)

## Part of the East Africa Coordination Stack

This MCP server is one of 32 tools in the Kenya coordination infrastructure.
Connect it to [`africa-coord-bus`](https://github.com/gabrielmahia/africa-coord-bus) —
the coordination event bus that routes signals between domains automatically.

```bash
pip install africa-coord-bus
```

All 32 servers: [pypi.org/user/gmahia](https://pypi.org/user/gmahia/)
Live demo: [coord-cascade-demo](https://github.com/gabrielmahia/coord-cascade-demo)
