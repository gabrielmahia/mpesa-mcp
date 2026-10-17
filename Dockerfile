FROM python:3.12-slim
LABEL org.opencontainers.image.title="mpesa-mcp"
LABEL org.opencontainers.image.description="MCP server for the M-Pesa Daraja API and Africa's Talking: sandbox by default; live money and SMS need confirmation"
LABEL org.opencontainers.image.source="https://github.com/gabrielmahia/mpesa-mcp"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.authors="Gabriel Mahia <contact@aikungfu.dev>"
RUN groupadd -r mcpuser && useradd -r -g mcpuser mcpuser
WORKDIR /app
# Latest published release, unpinned: this was pinned to 0.1.8, so Glama inspected an old release that exposed only 5 of the 23 tools.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir mpesa-mcp
USER mcpuser
# Sandbox by default; no credentials are baked in.
ENV MPESA_SANDBOX=true
ENV AT_USERNAME="sandbox"
ENTRYPOINT ["mpesa-mcp"]
