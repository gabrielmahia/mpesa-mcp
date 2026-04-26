# mpesa-mcp — Dockerfile for Glama sandbox evaluation
# Glama uses this to run security checks and assign quality scores
#
# Usage (local):
#   docker build -t mpesa-mcp .
#   docker run -e SANDBOX=true mpesa-mcp
#
# MCP config (after Glama release):
#   {"mcpServers": {"mpesa": {"command": "docker", "args": ["run", "-i", "--rm",
#     "-e", "MPESA_CONSUMER_KEY=...", "-e", "MPESA_CONSUMER_SECRET=...",
#     "gabrielmahia/mpesa-mcp"]}}}

FROM python:3.11-slim

# Metadata
LABEL org.opencontainers.image.title="mpesa-mcp"
LABEL org.opencontainers.image.description="MCP server for M-Pesa and Africa's Talking APIs"
LABEL org.opencontainers.image.source="https://github.com/gabrielmahia/mpesa-mcp"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.authors="Gabriel Mahia <contact@aikungfu.dev>"
LABEL org.opencontainers.image.version="0.1.8"

# Security: run as non-root
RUN groupadd -r mcpuser && useradd -r -g mcpuser mcpuser

WORKDIR /app

# Install dependencies efficiently
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Switch to non-root user
USER mcpuser

# Environment — all default to sandbox-safe values
ENV SANDBOX=true
ENV MPESA_CONSUMER_KEY=""
ENV MPESA_CONSUMER_SECRET=""
ENV MPESA_BUSINESS_SHORT_CODE=""
ENV MPESA_PASSKEY=""
ENV MPESA_CALLBACK_URL=""
ENV AT_USERNAME="sandbox"
ENV AT_API_KEY=""
ENV AT_SENDER_ID="MPESA"

# MCP servers communicate via stdio
ENTRYPOINT ["mpesa-mcp"]
