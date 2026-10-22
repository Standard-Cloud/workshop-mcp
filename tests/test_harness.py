"""Agent inspector harness: real merchant MCP servers in memory, canned OpenAI responses."""
import json

import httpx
import pytest

from conftest import load, mcp_server

pytestmark = pytest.mark.anyio
harness_mod = load("agent-inspector", "harness")

URLS = {
    "prix-malin": "http://localhost:9001/mcp",
    "hypermax": "http://localhost:9002/mcp",
    "bricopro": "http://localhost:9003/mcp",
}


class FakeLLM:
    """Records request bodies and answers with queued chat.completion payloads."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "small-model", "max_model_len": 4096}]})
        self.requests.append(json.loads(request.content))
        reply = self.replies.pop(0)
        if isinstance(reply, httpx.Response):
            return reply
        return httpx.Response(200, json=reply)


def completion(content="", tool_calls=None, prompt_tokens=100):
    message = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "object": "chat.completion",
        "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls" if tool_calls else "stop"}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": 10, "total_tokens": prompt_tokens + 10},
    }


def call(name, arguments, call_id="call-1"):
    args = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": args}}


@pytest.fixture
def make(monkeypatch):
    servers = {url: mcp_server(name, monkeypatch) for name, url in URLS.items()}

    def _make(*replies, **settings):
        llm = FakeLLM(*replies)
        config = harness_mod.Settings(base_url="http://llm/v1", **settings)
        h = harness_mod.Harness(
            config,
            http=httpx.AsyncClient(transport=httpx.MockTransport(llm.handler)),
            mcp_target=lambda url: servers[url],
        )
        return h, llm

    return _make


async def collect(stream):
    return [event async for event in stream]


def types(events):
    return [e["type"] for e in events]


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://example/v1")
    monkeypatch.setenv("LLM_MODEL", "big-model")
    monkeypatch.setenv("LLM_MAX_CONTEXT", "32768")
    monkeypatch.setenv("LLM_MAX_TOKENS", "2048")
    monkeypatch.setenv("LLM_MAX_ROUNDS", "12")
    s = harness_mod.Settings.from_env()
    assert (s.base_url, s.model, s.max_context, s.max_tokens, s.max_rounds) == (
        "http://example/v1", "big-model", 32768, 2048, 12)


async def test_model_and_context_are_detected_unless_configured(make):
    h, _ = make()
    assert await h.model_info() == {"model": "small-model", "max_context": 4096}
    h, _ = make(model="other", max_context=32768)
    assert await h.model_info() == {"model": "other", "max_context": 32768}


async def test_add_server_shows_discovery_and_namespaces_tools(make):
    h, _ = make()
    events = await collect(h.add_server(URLS["prix-malin"]))
    assert types(events) == ["mcp_initialize", "mcp_tools_list", "mcp_resources_list", "mcp_prompts_list", "context_change"]
    assert list(h.servers) == ["prix-malin"]
    names = [t["function"]["name"] for t in h.tool_definitions()]
    assert names == [
        "prix-malin__list_current_arrivals",
        "prix-malin__get_arrival_details",
        "prix-malin__check_purchase_feasibility",
    ]


async def test_without_servers_no_tools_are_sent(make):
    h, llm = make(completion("I have no merchant data."))
    events = await collect(h.chat("Price of cola?"))
    assert types(events) == ["user_message", "llm_request", "llm_response", "final_answer"]
    body = llm.requests[0]
    assert "tools" not in body
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][-1] == {"role": "user", "content": "Price of cola?"}
    assert body["model"] == "small-model"


async def test_server_instructions_are_added_to_system_prompt(make):
    h, llm = make(completion("ok"))
    await collect(h.add_server(URLS["hypermax"]))
    await collect(h.chat("hi"))
    assert "08:00-21:00" in llm.requests[0]["messages"][0]["content"]


async def test_tool_loop_calls_mcp_and_feeds_result_back(make):
    h, llm = make(
        completion(tool_calls=[call("hypermax__search_catalog", {"query": "cola"})]),
        completion("Cola costs 1.15 EUR at HyperMax."),
    )
    await collect(h.add_server(URLS["hypermax"]))
    events = await collect(h.chat("Price of cola?"))
    assert types(events) == [
        "user_message",
        "llm_request", "llm_response", "tool_calls", "mcp_call", "mcp_result",
        "llm_request", "llm_response", "final_answer",
    ]
    tool_message = llm.requests[1]["messages"][-1]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call-1"
    assert '"price_eur":1.15' in tool_message["content"]  # compact JSON
    assert "\n" not in tool_message["content"]
    assert events[-1]["data"]["content"] == "Cola costs 1.15 EUR at HyperMax."


async def test_model_is_stateless_every_request_resends_history(make):
    h, llm = make(
        completion(tool_calls=[call("hypermax__search_catalog", {"query": "cola"})]),
        completion("1.15 EUR"),
        completion("You asked about cola."),
    )
    await collect(h.add_server(URLS["hypermax"]))
    await collect(h.chat("Price of cola?"))
    await collect(h.chat("What did I ask?"))
    first, second, third = (r["messages"] for r in llm.requests)
    assert second[: len(first)] == first
    assert third[: len(second)] == second
    assert all(r["tools"] == llm.requests[0]["tools"] for r in llm.requests)


async def test_llm_request_event_counts_resent_and_new_messages(make):
    h, _ = make(completion("a"), completion("b"))
    await collect(h.chat("one"))
    events = await collect(h.chat("two"))
    request = next(e for e in events if e["type"] == "llm_request")
    assert request["data"]["resent_messages"] == 3  # system + user + assistant
    assert request["data"]["new_messages"] == 1


async def test_thinking_is_shown_but_not_kept_in_history(make):
    h, llm = make(completion("<think>\nThe user wants cola.\n</think>\n\nNo data."), completion("ok"))
    events = await collect(h.chat("cola?"))
    reasoning = next(e for e in events if e["type"] == "model_reasoning")
    assert "The user wants cola." in reasoning["data"]["reasoning"]
    await collect(h.chat("again"))
    assert llm.requests[1]["messages"][2] == {"role": "assistant", "content": "No data."}


async def test_llm_response_reports_context_usage(make):
    h, _ = make(completion("ok", prompt_tokens=1762))
    events = await collect(h.chat("hi"))
    response = next(e for e in events if e["type"] == "llm_response")
    assert response["data"]["usage"]["prompt_tokens"] == 1762
    assert response["data"]["max_context"] == 4096


async def test_remove_server_removes_its_tools(make):
    h, llm = make(completion("ok"))
    await collect(h.add_server(URLS["prix-malin"]))
    await collect(h.add_server(URLS["hypermax"]))
    h.remove_server("prix-malin")
    await collect(h.chat("hi"))
    assert all(t["function"]["name"].startswith("hypermax__") for t in llm.requests[0]["tools"])


async def test_tool_errors_go_back_to_the_model(make):
    h, llm = make(
        completion(tool_calls=[
            call("prix-malin__get_arrival_details", {"arrival_code": "CHIPS"}, "c1"),
            call("unknown__tool", {}, "c2"),
            call("prix-malin__list_current_arrivals", "{not json", "c3"),
        ]),
        completion("Chips are not sold."),
    )
    await collect(h.add_server(URLS["prix-malin"]))
    events = await collect(h.chat("chips?"))
    assert events[-1]["type"] == "final_answer"
    results = {m["tool_call_id"]: m["content"] for m in llm.requests[1]["messages"] if m["role"] == "tool"}
    assert "CHIPS" in results["c1"]
    assert "Unknown tool" in results["c2"]
    assert "Invalid JSON arguments" in results["c3"]
    mcp_result = next(e for e in events if e["type"] == "mcp_result")
    assert mcp_result["data"]["is_error"] is True


async def test_loop_stops_after_max_rounds(make):
    looping = [completion(tool_calls=[call("hypermax__search_catalog", {"query": "x"}, f"c{i}")]) for i in range(5)]
    h, llm = make(*looping, max_rounds=5)
    await collect(h.add_server(URLS["hypermax"]))
    events = await collect(h.chat("loop"))
    assert len(llm.requests) == 5
    assert events[-1]["type"] == "error"


async def test_llm_http_error_is_reported(make):
    h, _ = make(httpx.Response(400, json={"error": {"message": "maximum context length is 4096 tokens"}}))
    events = await collect(h.chat("hi"))
    assert events[-1]["type"] == "error"
    assert "maximum context length" in events[-1]["summary"]


async def test_attach_resource_adds_user_message_without_calling_model(make):
    h, llm = make()
    await collect(h.add_server(URLS["bricopro"]))
    events = await collect(h.attach_resource("bricopro", "bricopro://guides/compatibilite"))
    assert types(events) == ["resource_attached"]
    assert llm.requests == []
    assert h.history[-1]["role"] == "user"
    assert "BBQ-G300" in h.history[-1]["content"]


async def test_use_prompt_inserts_messages_then_runs_the_model(make):
    h, llm = make(completion("Here is a plan."))
    await collect(h.add_server(URLS["prix-malin"]))
    events = await collect(
        h.use_prompt("prix-malin", "find_lowest_cost_meal", {"guests": "10", "budget_eur": "40", "shopping_time": "16:30"})
    )
    assert types(events)[0] == "prompt_used"
    assert events[-1]["type"] == "final_answer"
    assert "10 guests" in llm.requests[0]["messages"][1]["content"]


async def test_reset_clears_history_but_keeps_servers(make):
    h, _ = make(completion("ok"))
    await collect(h.add_server(URLS["hypermax"]))
    await collect(h.chat("hi"))
    h.reset()
    assert h.history == []
    assert list(h.servers) == ["hypermax"]
    assert h.requests_sent == 0


async def test_empty_final_answer_is_made_visible(make):
    h, _ = make(completion(""))
    events = await collect(h.chat("hi"))
    response = next(e for e in events if e["type"] == "llm_response")
    assert "finish_reason: stop" in response["summary"]
    assert "no answer text" in events[-1]["summary"]
    assert h.history[-1] == {"role": "assistant", "content": ""}
