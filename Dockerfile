# mpesa-mcp — Dockerfile for Glama sandbox build and evaluation
# Glama uses this to run security checks and assign quality/security scores.
#
# Local usage:
#   docker build -t mpesa-mcp .
#   docker run -e MPESA_SANDBOX=true -e MPESA_CONSUMER_KEY=... mpesa-mcp

FROM python:3.11-slim

LABEL org.opencontainers.image.title="mpesa-mcp"
LABEL org.opencontainers.image.description="MCP server for M-Pesa and Africa's Talking APIs"
LABEL org.opencontainers.image.source="https://github.com/gabrielmahia/mpesa-mcp"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.authors="Gabriel Mahia <contact@aikungfu.dev>"
LABEL org.opencontainers.image.version="0.1.8"

# Non-root for security
RUN groupadd -r mcpuser && useradd -r -g mcpuser mcpuser

WORKDIR /app

# Install the package from PyPI (avoids src/ copy issues)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir mpesa-mcp==0.1.8

USER mcpuser

# Env vars — all match server.py exactly
# Sandbox-safe defaults — no real money moves unless MPESA_SANDBOX=false
ENV MPESA_SANDBOX=true
ENV MPESA_CONSUMER_KEY=""
ENV MPESA_CONSUMER_SECRET=""
ENV MPESA_SHORTCODE=""
ENV MPESA_PASSKEY=""
ENV MPESA_CALLBACK_URL=""
ENV AT_USERNAME="sandbox"
ENV AT_API_KEY=""
ENV MPESA_INITIATOR_NAME=""
ENV MPESA_SECURITY_CREDENTIAL=""

# MCP servers use stdio transport
ENTRYPOINT ["mpesa-mcp"]
