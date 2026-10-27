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
[![NSA CSI guidance: self-assessed](https://img.shields.io/badge/NSA%20CSI%20U%2FOO%2F6030316--26-self--assessed%2C%20not%20certified-lightgrey)](https://www.nsa.gov/Portals/75/documents/Cybersecurity/CSI_MCP_SECURITY.pdf)

[![mpesa-mcp MCP server](https://glama.ai/mcp/servers/gabrielmahia/mpesa-mcp/badges/card.svg)](https://glama.ai/mcp/servers/gabrielmahia/mpesa-mcp)


## Models
This server does not recommend, certify or benchmark any model, and `get_model_hint()` is kept only for compatibility (it returns neutral guidance). Use a model that follows tool schemas reliably, rehearse in the sandbox first, and keep a person approving every money-moving or messaging call: in live mode those tools need `confirm_send=true` and are capped (`MPESA_MAX_AMOUNT_KES`, default KES 100,000; `MPESA_MAX_SMS_RECIPIENTS`, default 50).

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



## Security: how this maps to the NSA's MCP guidance (self-assessed, not certified)

`mpesa-mcp` was reviewed against **NSA CSI U/OO/6030316-26 (May 2026)**, the NSA Artificial Intelligence Security Center's Cybersecurity Information Sheet on Model Context Protocol security. That sheet is guidance, not a certifiable standard, so the table below is this project's own self-assessment, not an audit or a certification.

| Control area | What this server does |
|---|---|
| Parameter validation | Kenyan phone numbers are normalised and validated; amounts must be positive and within the configured limits |
| Audit logging | One structured log line per tool call; phone numbers are logged as a truncated SHA-256 hash, other identifiers as given; a terminal line records how each money-out call ended |
| Spend limits | A per-payment cap, a per-session budget, an optional recipient allowlist, and confirmation required in live mode (see Bounded authorisation below) |
| Token lifecycle | The Daraja OAuth token is cached with its expiry and refreshed automatically |
| Error handling | Daraja API errors are returned as structured results; an unexpected exception is logged by type only and re-raised, and the MCP framework reports it to the client |
| HTTPS | All Daraja API calls use HTTPS |
| Secrets | Live credentials come from environment variables; the Safaricom sandbox test shortcode and passkey in this README are published examples, not secrets |

See [SECURITY.md](./SECURITY.md) for how to report a vulnerability.

> **Reference:** [NSA CSI_MCP_SECURITY.pdf](https://www.nsa.gov/Portals/75/documents/Cybersecurity/CSI_MCP_SECURITY.pdf) (May 2026, UNCLASSIFIED)

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

New Daraja account, or setting this up on a new machine? Follow the [sandbox setup guide](https://github.com/gabrielmahia/mpesa-python/blob/main/docs/SANDBOX_SETUP.md): it records the verified procedure (create the app with only **Lipa Na M-Pesa Sandbox** ticked, use the published test shortcode and passkey, point `MPESA_CALLBACK_URL` at a public HTTPS address you can watch) and what a healthy result looks like. Consumer keys cannot be shared, so each developer creates their own free sandbox app.

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

These tests check this server's behaviour. This README makes no claim about how accurate any model is when it uses this server.

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

**Swahili and translation** (arXiv:2509.04516, 2025): in a small news-classification experiment, a Swahili-native BERT model made 0.36% errors against 1.47% for an English model applied to machine-translated Swahili, so native beat translate-then-classify on that task. This server's tool descriptions are written so they can be read in Swahili as well as English; no effect of that has been measured here.

**MCP security research** (arXiv:2603.18063, arXiv:2603.21642, 2026): Prompt injection via tool descriptions is the primary MCP attack vector. mpesa-mcp mitigates this through static, versioned tool descriptions and strict input validation.

**Related infrastructure:**
- [wapimaji-mcp](https://github.com/gabrielmahia/wapimaji-mcp) — Kenya drought-response MCP (simulated data)
- [civic-agent-kit](https://github.com/gabrielmahia/civic-agent-kit) — Kenya civic data MCP
- [swahili-health-mcp](https://github.com/gabrielmahia/swahili-health-mcp) — Kenya DHS 2022 county health indicators MCP
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
| [wapimaji-mcp](https://github.com/gabrielmahia/wapimaji-mcp) | `pip install wapimaji-mcp` | Simulated drought phases and SMS alerts MCP server (no real NDMA data yet) |
| [civic-agent-kit](https://github.com/gabrielmahia/civic-agent-kit) | `pip install civic-agent-kit` | East African civic AI SDK |
## Related packages

All MIT · All part of the East African civic AI stack

| Package | Install | Description |
|---------|---------|-------------|
| [wapimaji-mcp](https://github.com/gabrielmahia/wapimaji-mcp) | `pip install wapimaji-mcp` | Simulated drought phases and SMS alerts MCP server (no real NDMA data yet) |
| [kenya-health-mcp](https://github.com/gabrielmahia/kenya-health-mcp) | `pip install kenya-health-mcp` | Kenya health data MCP — SHA/SHIF, facilities, maternal, rights |
| [civic-agent-kit](https://github.com/gabrielmahia/civic-agent-kit) | `pip install civic-agent-kit` | East African civic AI SDK |

Full portfolio: [gabrielmahia.github.io](https://gabrielmahia.github.io)

## Part of the East Africa Coordination Stack

This MCP server is part of the Kenya coordination infrastructure.
Connect it to [`africa-coord-bus`](https://github.com/gabrielmahia/africa-coord-bus) —
the coordination event bus that routes signals between domains automatically.

```bash
pip install africa-coord-bus
```

All servers: [pypi.org/user/gmahia](https://pypi.org/user/gmahia/)
Live demo: [coord-cascade-demo](https://github.com/gabrielmahia/coord-cascade-demo)

## IP & Collaboration

MIT licensed. Feedback via GitHub Issues only — pull requests are not accepted. Demo data is labeled DEMO and is not suitable for operational decisions. Full policy: [docs/architecture/IP_POLICY.md](docs/architecture/IP_POLICY.md). Security reports: see [SECURITY.md](SECURITY.md).

<!-- interconnect:v2 -->
## Part of the East Africa coordination stack

- **Install & run:** `pip install reli-cli && reli list` — the MCP servers on the [official MCP Registry](https://registry.modelcontextprotocol.io) under `io.github.gabrielmahia`
- **Evaluate any model on Swahili agent tasks:** [kipimo](https://github.com/gabrielmahia/kipimo) · [dataset](https://huggingface.co/datasets/gmahia/kipimo) · [leaderboard](https://huggingface.co/spaces/gmahia/kipimo-leaderboard)
- **Coordinate across servers:** [africa-coord-bus](https://pypi.org/project/africa-coord-bus/) — offline-first event bus with a built-in Kenya routing table
- **Datasets:** [huggingface.co/gmahia](https://huggingface.co/gmahia) · **Docs hub:** [nairobi-stack](https://github.com/gabrielmahia/nairobi-stack)

Model-agnostic by design: closed APIs, open-weight models, and small distilled models are all first-class citizens.
<!-- /interconnect:v2 -->

## Safety limits for tools that send money out (0.3.0, breaking in live mode)

A language model can be talked into paying anyone any amount: prompt injection against payment tools is a documented attack on agent payment protocols (AP2, x402). So in **live** mode (`MPESA_SANDBOX=false`) the eight outflow tools (`mpesa_b2c`, `mpesa_business_paybill`, `mpesa_business_buygoods`, `mpesa_business_pochi`, `mpesa_reversal`, `mpesa_tax_remittance`, `mpesa_b2b_express_checkout`, `airtime_send`) are bounded:

- **Confirmation:** they refuse unless called with `confirm_send=true`. The agent must show the user the recipient and amount and set it only after explicit approval.
- **Cap:** amounts above `MPESA_MAX_AMOUNT_KES` (default **20,000**; `0` = no cap) are refused.
- **Session budget:** one server process may authorise at most `MPESA_SESSION_BUDGET_KES` in total (default **50,000**; `0` = no budget). The cap bounds one payment; the budget bounds the **sum**, so an agent cannot repeat a capped payment without limit. It is counted when a payment is authorised and is not refunded if the call later fails (a timed-out call may still have moved money), and it resets only when the server restarts. Only the operator, not the model, can change it. If you legitimately move more than 300,000 KES in one session, set it higher.
- **The person confirms, not the model (0.5.0):** for the eight money-out tools in live mode the server itself asks **you**, through your MCP client, to approve the exact payment (recipient in full, amount, reference) before anything runs, using MCP elicitation in both protocol eras. The model cannot answer for you: it can say `confirm_send=true`, and you can still decline. Your approval is bound to that exact call (a different amount or recipient needs a new approval), works once, and expires after five minutes. Payments the server would refuse anyway (over the cap, over the budget, not on the allowlist) never reach you. `MPESA_CONFIRM_MODE`: `auto` (default: ask when your client can answer; otherwise fall back to the `confirm_send` parameter), `elicit` (strict: refuse when your client cannot show a prompt) or `param` (the old behaviour). The sandbox is never prompted. Not every client supports elicitation yet; if yours does not, use `elicit` mode to refuse instead of falling back, and keep your client's own per-call approval on.
- **Allowed recipients:** set `MPESA_ALLOWED_RECIPIENTS` (comma-separated phone numbers, paybills and tills) and the money-out tools will pay only those recipients; anything else is refused. Phone numbers match in any Kenyan format. Unset means no restriction, and for production use a list is recommended: scoping who can be paid is the same idea as a merchant-scoped payment token or a named-merchant reservation. Reversal and tax remittance have no free recipient, so the list does not apply to them.
- **Session report:** the `mpesa_session_report` tool (read-only) returns the limits, what has been spent and what is left, and the last ten authorisations or refusals with recipients masked, from the server's own record. Use it to check the budget before a payment, and to verify what the server actually authorised instead of relying on what a model says it did.

#### Bound the loss outside the tool as well

These guards run inside the tool, the layer an agent controls. Two checks sit outside it, and you should use both, and keep the limits small:

1. **`confirm_send` is supplied by the model itself**, so on its own it is not an independent check. Since 0.5.0 the server asks you directly through your client (see above); where your client cannot show that prompt, keep your MCP client's own per-call approval on for the eight money-out tools and never set them to "always allow".
2. **Bound the loss in the payment rail.** Pay out from a dedicated business shortcode or working account that holds only what you are prepared to lose, and use whatever initiator limits or approval (maker-checker) controls your M-PESA organisation account offers; this server cannot see them, so check Safaricom's current documentation.

This is the layered design that India's agentic-payment pilots (a pre-funded, merchant-scoped reservation and delegated limits enforced by the network) and Alipay's agent payments (a user-set threshold below which an agent may pay and above which a person confirms, a way to review and revoke an agent's authority, and a loss guarantee) arrived at independently.

3. **Start small.** The defaults here (20,000 KES per payment, 50,000 per session, lowered in 0.5.0 from 100,000 and 300,000) are ceilings, not recommendations. Brazilian banks that let customers pay by voice or text through an AI assistant on WhatsApp start at roughly R$200 to R$800 per payment, ask for a confirmation on each one, and send anything larger to the bank's own app: the same order of magnitude as the defaults here. Set `MPESA_MAX_AMOUNT_KES` and `MPESA_SESSION_BUDGET_KES` to the smallest figures you actually need, and raise them only when you have a reason.
- **Opt-out:** `MPESA_REQUIRE_CONFIRMATION=false` removes the confirmation requirement for fully automated setups you control. Do that only deliberately.
- The **sandbox is never restricted**. Customer-approved flows (STK Push, Ratiba, Bill Manager) are unchanged: the customer approves on their handset.
