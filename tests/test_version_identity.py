"""One version, four places: pyproject, server.json, glama.json and what the running server reports must agree."""
import json
import pathlib
import re
from importlib.metadata import version

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _pyproject_version():
    return re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.MULTILINE).group(1)


def test_the_installed_package_matches_pyproject():
    assert version("mpesa-mcp") == _pyproject_version()


def test_server_json_and_glama_json_carry_the_same_version():
    pv = _pyproject_version()
    srv = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    assert srv["version"] == pv and all(p["version"] == pv for p in srv.get("packages", []))
    assert json.loads((ROOT / "glama.json").read_text(encoding="utf-8"))["version"] == pv


def test_the_running_server_reports_the_package_version_not_the_library_version():
    from mpesa_mcp import __version__
    from mpesa_mcp.server import mcp

    assert __version__ == _pyproject_version() and mcp.version == _pyproject_version()
