# mpesa-mcp

> MCP server for East African fintech APIs — M-Pesa (Safaricom Daraja) and Africa's Talking

Give your AI agent the ability to trigger M-Pesa payments, check transaction status, send SMS, and top up airtime across 20+ African telecom networks.

[![Tests](https://github.com/gabrielmahia/mpesa-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/gabrielmahia/mpesa-mcp/actions)
[![PyPI](https://img.shields.io/pypi/v/mpesa-mcp)](https://pypi.org/project/mpesa-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

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

MIT — © 2026 Gabriel Mahia
