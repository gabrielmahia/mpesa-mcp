"""Shared by the money-tool tests."""
from mpesa_mcp import server


class Reached(Exception):
    """Raised by the stubbed network so a test can tell that a payment reached it."""


def fn(name):
    return (getattr(server, name).fn if hasattr(getattr(server, name), "fn") else getattr(server, name))
