"""Minimal agent harness: an OpenAI-compatible model + MCP servers, narrated step by step.

Every public method yields events ({type, title, summary, data}) so the UI can show
what the harness does on behalf of the (stateless) model.
"""
import json
import os
import re
from collections.abc import AsyncIterator, Callable
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx
from mcp import Client

DEFAULT_SYSTEM_PROMPT = (
    "You are a shopping assistant. Answer only from tool results: call the merchant tools to get "
    "prices, stock and opening hours, then answer briefly. Prices are in EUR. "
    "If no tool can answer, say so instead of guessing."
)


@dataclass
class Settings:
    base_url: str = "http://192.168.1.20:5004/v1"
    api_key: str = ""
    model: str = ""  # empty: first model listed by /models
    max_context: int = 0  # 0: max_model_len reported by /models
    max_tokens: int = 4096
    max_rounds: int = 10  # model requests per user turn, guards against endless tool loops
    system_prompt: str = DEFAULT_SYSTEM_PROMPT

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            base_url=os.environ.get("LLM_BASE_URL", cls.base_url),
            api_key=os.environ.get("LLM_API_KEY", ""),
            model=os.environ.get("LLM_MODEL", ""),
            max_context=int(os.environ.get("LLM_MAX_CONTEXT", "0")),
            max_tokens=int(os.environ.get("LLM_MAX_TOKENS", str(cls.max_tokens))),
            max_rounds=int(os.environ.get("LLM_MAX_ROUNDS", str(cls.max_rounds))),
        )

    def public(self) -> dict:
        return {k: v for k, v in asdict(self).items() if k != "api_key"} | {"api_key_set": bool(self.api_key)}


@dataclass
class McpServer:
    name: str
    url: str
    instructions: str | None
    tools: list[dict] = field(default_factory=list)
    resources: list[dict] = field(default_factory=list)
    prompts: list[dict] = field(default_factory=list)


def event(type_: str, title: str, summary: str = "", **data: Any) -> dict:
    return {"type": type_, "title": title, "summary": summary, "data": data}


def dump(model) -> dict:
    return model.model_dump(mode="json", by_alias=True, exclude_none=True)


def compact(text: str) -> str:
    try:
        return json.dumps(json.loads(text), ensure_ascii=False, separators=(",", ":"))
    except ValueError:
        return text


def split_thinking(content: str | None) -> tuple[str, str]:
    """Qwen-style models put their reasoning in <think>...</think> before the answer."""
    content = content or ""
    match = re.search(r"<think>(.*?)</think>", content, re.S)
    if not match:
        return "", content.strip()
    return match.group(1).strip(), (content[: match.start()] + content[match.end():]).strip()


class Harness:
    def __init__(
        self,
        settings: Settings,
        http: httpx.AsyncClient | None = None,
        mcp_target: Callable[[str], Any] = lambda url: url,
    ):
        self.settings = settings
        self.http = http or httpx.AsyncClient(timeout=300)
        self.mcp_target = mcp_target  # tests swap URLs for in-memory servers
        self.servers: dict[str, McpServer] = {}
        self.history: list[dict] = []
        self.requests_sent = 0
        self._known_messages = 0

    # ---- model -------------------------------------------------------------

    async def model_info(self) -> dict:
        model, max_context = self.settings.model, self.settings.max_context
        if not model or not max_context:
            listed = (await self.http.get(f"{self.settings.base_url}/models", headers=self._headers())).json()["data"]
            entry = next((m for m in listed if m["id"] == model), listed[0])
            model = model or entry["id"]
            max_context = max_context or entry.get("max_model_len", 0)
        return {"model": model, "max_context": max_context}

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.settings.api_key}"} if self.settings.api_key else {}

    def system_prompt(self) -> str:
        parts = [self.settings.system_prompt]
        parts += [f"[{s.name} server instructions] {s.instructions}" for s in self.servers.values() if s.instructions]
        return "\n\n".join(parts)

    def tool_definitions(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": f"{server.name}__{tool['name']}",
                    "description": tool.get("description", ""),
                    "parameters": tool["inputSchema"],
                },
            }
            for server in self.servers.values()
            for tool in server.tools
        ]

    async def build_request(self) -> dict:
        body = {
            "model": (await self.model_info())["model"],
            "messages": [{"role": "system", "content": self.system_prompt()}, *self.history],
            "max_tokens": self.settings.max_tokens,
        }
        if tools := self.tool_definitions():
            body["tools"] = tools
        return body

    # ---- MCP ---------------------------------------------------------------

    def _client(self, url: str) -> Client:
        return Client(self.mcp_target(url))

    async def add_server(self, url: str) -> AsyncIterator[dict]:
        try:
            async with self._client(url) as c:
                info = c.server_info
                name = re.sub(r"[^A-Za-z0-9_-]", "-", info.name if info else url)
                yield event(
                    "mcp_initialize", f"initialize → {name}",
                    "The harness opens an MCP connection; the server introduces itself and its capabilities.",
                    url=url, server_info=dump(info) if info else None,
                    capabilities=dump(c.server_capabilities), instructions=c.instructions,
                )
                server = McpServer(name=name, url=url, instructions=c.instructions)
                server.tools = [dump(t) for t in (await c.list_tools()).tools]
                yield event(
                    "mcp_tools_list", f"tools/list → {len(server.tools)} tools",
                    "Tools are actions the MODEL may decide to call.",
                    tools=server.tools,
                )
                server.resources = [dump(r) for r in (await c.list_resources()).resources]
                yield event(
                    "mcp_resources_list", f"resources/list → {len(server.resources)} resources",
                    "Resources are documents the USER can attach to the conversation.",
                    resources=server.resources,
                )
                server.prompts = [dump(p) for p in (await c.list_prompts()).prompts]
                yield event(
                    "mcp_prompts_list", f"prompts/list → {len(server.prompts)} prompts",
                    "Prompts are templates the USER can pick to start a task.",
                    prompts=server.prompts,
                )
        except Exception as exc:
            yield event("error", f"Cannot connect to {url}", f"{type(exc).__name__}: {exc}")
            return
        self.servers[name] = server
        added = [d for d in self.tool_definitions() if d["function"]["name"].startswith(f"{name}__")]
        size = len(json.dumps(added, ensure_ascii=False))
        yield event(
            "context_change", f"{len(added)} tool definitions added to the model context",
            f"From now on, every request to the model carries these {len(added)} definitions "
            f"(~{size} characters) and the server instructions. Discovery only changes what is sent; "
            "the model itself learns nothing.",
            tool_definitions=added, characters=size, system_prompt=self.system_prompt(),
        )

    def remove_server(self, name: str) -> None:
        self.servers.pop(name, None)

    async def call_tool(self, server: McpServer, tool: str, arguments: dict) -> tuple[str, bool]:
        async with self._client(server.url) as c:
            result = await c.call_tool(tool, arguments)
        text = "\n".join(getattr(part, "text", "") for part in result.content)
        return text, result.is_error

    async def attach_resource(self, server_name: str, uri: str) -> AsyncIterator[dict]:
        async with self._client(self.servers[server_name].url) as c:
            contents = (await c.read_resource(uri)).contents
        text = "\n".join(getattr(part, "text", "") for part in contents)
        message = {"role": "user", "content": f"[Attached resource {uri}]\n\n{text}"}
        self.history.append(message)
        yield event(
            "resource_attached", f"resources/read {uri}",
            "The USER attached this document: the harness pastes it into the history as a user message. "
            "The model will see it in the next request.",
            uri=uri, message=message,
        )

    async def use_prompt(self, server_name: str, name: str, arguments: dict) -> AsyncIterator[dict]:
        async with self._client(self.servers[server_name].url) as c:
            prompt = await c.get_prompt(name, arguments)
        messages = [{"role": m.role, "content": getattr(m.content, "text", "")} for m in prompt.messages]
        self.history.extend(messages)
        yield event(
            "prompt_used", f"prompts/get {name}",
            "The USER picked a server prompt: the harness fills the template and adds it to the history.",
            arguments=arguments, messages=messages,
        )
        async for e in self._run():
            yield e

    # ---- agent loop --------------------------------------------------------

    async def chat(self, text: str) -> AsyncIterator[dict]:
        message = {"role": "user", "content": text}
        self.history.append(message)
        yield event("user_message", "User prompt", text, message=message)
        async for e in self._run():
            yield e

    def reset(self) -> None:
        self.history = []
        self.requests_sent = 0
        self._known_messages = 0

    async def _run(self) -> AsyncIterator[dict]:
        for _ in range(self.settings.max_rounds):
            body = await self.build_request()
            self.requests_sent += 1
            resent = min(self._known_messages, len(body["messages"]))
            new = len(body["messages"]) - resent
            self._known_messages = len(body["messages"])
            yield event(
                "llm_request", f"Request #{self.requests_sent} → model",
                f"{len(body['messages'])} messages ({resent} re-sent, {new} new) + "
                f"{len(body.get('tools', []))} tool definitions. The model keeps no memory: "
                "the harness sends the whole conversation every time.",
                request_number=self.requests_sent, resent_messages=resent, new_messages=new, body=body,
            )

            try:
                response = await self.http.post(
                    f"{self.settings.base_url}/chat/completions", json=body, headers=self._headers()
                )
            except httpx.HTTPError as exc:
                yield event("error", "Model unreachable", f"{type(exc).__name__}: {exc}")
                return
            if response.status_code != 200:
                yield event("error", f"Model error HTTP {response.status_code}", response.text[:1000])
                return
            payload = response.json()
            message = payload["choices"][0]["message"]
            usage = payload.get("usage", {})
            max_context = (await self.model_info())["max_context"]
            reasoning, answer = split_thinking(message.get("content"))
            reasoning = reasoning or message.get("reasoning") or message.get("reasoning_content") or ""
            tool_calls = message.get("tool_calls") or []
            finish = payload["choices"][0].get("finish_reason")
            yield event(
                "llm_response", "Model reply",
                f"{'asks for ' + str(len(tool_calls)) + ' tool call(s)' if tool_calls else 'final answer'} · "
                f"finish_reason: {finish} · context {usage.get('prompt_tokens', '?')} / {max_context or '?'} tokens",
                usage=usage, max_context=max_context, raw=payload,
            )
            if reasoning:
                yield event(
                    "model_reasoning", "Model reasoning (not kept)",
                    "Shown for teaching; the harness drops it from the history to save context.",
                    reasoning=reasoning,
                )

            self._known_messages += 1  # the model's reply is part of what gets re-sent next time
            if not tool_calls:
                self.history.append({"role": "assistant", "content": answer})
                shown = answer or f"(The model returned no answer text, finish_reason: {finish}. Ask again or rephrase.)"
                yield event("final_answer", "Final answer", shown, content=answer)
                return

            assistant = {"role": "assistant", "content": answer, "tool_calls": tool_calls}
            self.history.append(assistant)
            yield event(
                "tool_calls", f"The model asks the harness to call {len(tool_calls)} tool(s)",
                ", ".join(tc["function"]["name"] for tc in tool_calls) + ". The model cannot call anything "
                "itself: it only writes a request, the harness executes it.",
                tool_calls=tool_calls,
            )
            for tc in tool_calls:
                async for e in self._execute(tc):
                    yield e

        yield event("error", f"Stopped after {self.settings.max_rounds} model requests", "The harness limits the loop.")

    async def _execute(self, tool_call: dict) -> AsyncIterator[dict]:
        name = tool_call["function"]["name"]
        server_name, _, tool = name.partition("__")
        server = self.servers.get(server_name)
        try:
            arguments = json.loads(tool_call["function"].get("arguments") or "{}")
        except ValueError:
            arguments = None

        if server is None or tool not in {t["name"] for t in server.tools}:
            content, is_error = f"Unknown tool '{name}'. Available: {[d['function']['name'] for d in self.tool_definitions()]}", True
        elif not isinstance(arguments, dict):
            content, is_error = f"Invalid JSON arguments for '{name}': {tool_call['function'].get('arguments')}", True
        else:
            yield event(
                "mcp_call", f"tools/call {tool} → {server.name}",
                f"The harness sends a JSON-RPC request to {server.url}.",
                server=server.name, url=server.url,
                jsonrpc={"jsonrpc": "2.0", "method": "tools/call", "params": {"name": tool, "arguments": arguments}},
            )
            try:
                content, is_error = await self.call_tool(server, tool, arguments)
            except Exception as exc:
                content, is_error = f"MCP call failed: {type(exc).__name__}: {exc}", True

        message = {"role": "tool", "tool_call_id": tool_call["id"], "content": compact(content)}
        self.history.append(message)
        yield event(
            "mcp_result", f"Result of {name}" + (" (error)" if is_error else ""),
            "Added to the history as a 'tool' message (compact JSON) for the next request.",
            is_error=is_error, raw=content, message=message,
        )
