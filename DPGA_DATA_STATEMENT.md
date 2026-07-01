# Data Statement — mpesa-mcp (DPGA GID0093741)

## Architecture

mpesa-mcp is an MCP server that wraps the Safaricom Daraja API and
Africa's Talking SMS/Airtime APIs. It does not train, fine-tune, or
deploy any AI model. It exposes payment and communication APIs as
MCP tools callable by AI agents.

## Data Handling

**What data passes through:**
- M-PESA phone numbers and transaction amounts (transient, not stored)
- SMS messages sent via Africa's Talking (not stored after delivery)
- Transaction status queries (transient responses from Daraja API)

**What is NOT stored:**
- No phone numbers are persisted by this server
- No transaction history is logged by this package
- No personal data is retained beyond the duration of a tool call

## No Training Data

This server contains no machine learning model and uses no training data.
The AI context is the language model calling its tools (e.g., Claude Sonnet 5),
not any model embedded in this package.

## Open Standards Used

- Model Context Protocol (MCP) — AAIF/Linux Foundation open standard
- JSON-RPC 2.0 — public standard
- REST/HTTP — public standard
- Safaricom Daraja API — publicly documented API

## DPGA Review

GID0093741 — UNDER REVIEW  
Submitted: 2025  
DPG Standard version: 2025 (including AI systems)

*Last updated: July 1, 2026*
