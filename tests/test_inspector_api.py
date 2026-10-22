"""Agent inspector web API: NDJSON event streams over the harness."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from conftest import load, mcp_server

URL = "http://localhost:9002/mcp"


@pytest.fixture
def client(monkeypatch):
    app_mod = load("agent-inspector", "app")
    hypermax = mcp_server("hypermax", monkeypatch)
    replies = [
        {"choices": [{"message": {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function",
             "function": {"name": "hypermax__search_catalog", "arguments": '{"query": "cola"}'}}]}}],
         "usage": {"prompt_tokens": 900}},
        {"choices": [{"message": {"role": "assistant", "content": "1.15 EUR"}}], "usage": {"prompt_tokens": 1000}},
    ]

    def llm(request):
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "small-model", "max_model_len": 4096}]})
        return httpx.Response(200, json=replies.pop(0))

    monkeypatch.setattr(app_mod, "harness", app_mod.Harness(
        app_mod.Settings(base_url="http://llm/v1"),
        http=httpx.AsyncClient(transport=httpx.MockTransport(llm)),
        mcp_target=lambda url: hypermax,
    ))
    return TestClient(app_mod.app)


def events(response):
    assert response.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in response.text.splitlines() if line]


def test_index_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "MCP Agent Inspector" in r.text


def test_state_shows_settings_without_api_key(client):
    state = client.get("/api/state").json()
    assert state["settings"]["model"] == ""
    assert state["model"] == {"model": "small-model", "max_context": 4096}
    assert "api_key" not in state["settings"]
    assert state["servers"] == [] and state["history"] == []


def test_settings_update(client):
    r = client.post("/api/settings", json={"model": "big", "max_context": 32768, "max_tokens": 256, "api_key": "k"})
    assert r.status_code == 200
    s = client.get("/api/state").json()["settings"]
    assert (s["model"], s["max_context"], s["max_tokens"], s["api_key_set"]) == ("big", 32768, 256, True)


def test_add_server_streams_discovery_then_lists_it(client):
    types = [e["type"] for e in events(client.post("/api/servers", json={"url": URL}))]
    assert types[0] == "mcp_initialize" and types[-1] == "context_change"
    server = client.get("/api/state").json()["servers"][0]
    assert server["name"] == "hypermax"
    assert len(server["tools"]) == 3 and len(server["resources"]) == 1 and len(server["prompts"]) == 1


def test_chat_streams_the_whole_loop(client):
    client.post("/api/servers", json={"url": URL})
    stream = events(client.post("/api/chat", json={"message": "Price of cola?"}))
    assert stream[-1] == {"type": "final_answer", "title": "Final answer", "summary": "1.15 EUR",
                          "data": {"content": "1.15 EUR"}}
    assert "mcp_call" in [e["type"] for e in stream]
    assert len(client.get("/api/state").json()["history"]) == 4  # user, assistant(tool_calls), tool, assistant


def test_attach_resource_and_reset(client):
    client.post("/api/servers", json={"url": URL})
    stream = events(client.post("/api/resources/attach",
                                json={"server": "hypermax", "uri": "hypermax://catalog/categories"}))
    assert stream[0]["type"] == "resource_attached"
    assert len(client.get("/api/state").json()["history"]) == 1
    client.post("/api/reset")
    assert client.get("/api/state").json()["history"] == []


def test_remove_server(client):
    client.post("/api/servers", json={"url": URL})
    assert client.delete("/api/servers/hypermax").status_code == 200
    assert client.get("/api/state").json()["servers"] == []
