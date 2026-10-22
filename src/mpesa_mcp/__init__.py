"""mpesa-mcp — MCP server for M-Pesa and Africa's Talking APIs."""

from importlib.metadata import PackageNotFoundError, version

try:  # the installed package version: the server reports this, not the library's
    __version__ = version("mpesa-mcp")
except PackageNotFoundError:  # a source tree that was never installed
    __version__ = "0+unknown"

from .server import mcp  # noqa: E402

__all__ = ["mcp", "__version__"]
