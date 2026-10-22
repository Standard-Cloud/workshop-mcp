import importlib.util
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent


def load(merchant: str, module: str):
    """Merchant folders contain hyphens, so modules are loaded by file path."""
    path = ROOT / merchant / f"{module}.py"
    spec = importlib.util.spec_from_file_location(f"{merchant.replace('-', '_')}_{module}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def api_client(merchant: str) -> TestClient:
    return TestClient(load(merchant, "api").app)


def mcp_server(merchant: str, monkeypatch: pytest.MonkeyPatch):
    """Load a merchant MCP server wired to its REST API in memory (no network)."""
    app = load(merchant, "api").app
    server = load(merchant, "mcp_server")
    monkeypatch.setattr(
        server,
        "api_client",
        lambda: httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://api"),
    )
    return server.mcp


@pytest.fixture
def anyio_backend():
    return "asyncio"


def result_json(result):
    """Parse the JSON payload of a successful tool call."""
    assert not result.is_error, result.content[0].text
    return json.loads(result.content[0].text)
