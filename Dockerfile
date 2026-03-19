FROM python:3.11-slim

WORKDIR /app

# Install mpesa-mcp from PyPI
RUN pip install --no-cache-dir mpesa-mcp==0.1.1

# Environment variables — set via MCP client configuration
ENV MPESA_CONSUMER_KEY=""
ENV MPESA_CONSUMER_SECRET=""
ENV MPESA_SHORTCODE=""
ENV MPESA_PASSKEY=""
ENV MPESA_ENV="sandbox"
ENV AT_API_KEY=""
ENV AT_USERNAME="sandbox"

# Run the MCP server (stdio transport)
ENTRYPOINT ["mpesa-mcp"]
