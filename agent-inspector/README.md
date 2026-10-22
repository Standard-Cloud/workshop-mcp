# MCP Agent Inspector — instructor demo

**Instructor-only tool, not used by students.** A minimal agent harness with a web UI that narrates every step between an OpenAI-compatible model and the merchant MCP servers. Use it on the projector, during "02 — Why MCP?", to show what tools like Copilot do behind the scenes.

What students should take away:

- **The model is stateless.** Every request re-sends the whole conversation; the right panel highlights what is new.
- **The harness does the work.** The model only *writes* a tool-call request; the harness calls the MCP server and pastes the result back into the history.
- **Discovery only changes the context.** Adding a server adds tool definitions and server instructions to every request (watch the token gauge grow); the model learns nothing.
- **Tools vs resources vs prompts.** The model picks tools; *you* attach resources and pick prompts.

## Run

Runs on the instructor's machine (it needs network access to the model; a Codespace cannot reach a local network).

```bash
pip install -r requirements.txt
bash scripts/start.sh                       # the 3 APIs + 3 MCP servers
python agent-inspector/app.py               # http://127.0.0.1:8090
```

Or **Terminal → Run Task → Inspector: start (instructor)**.

## Settings

Environment variables, also editable live in the UI (**Model settings**, bottom left):

| Variable | Default | Meaning |
|---|---|---|
| `LLM_BASE_URL` | `http://192.168.1.20:5004/v1` | Any OpenAI-compatible Chat Completions endpoint |
| `LLM_MODEL` | *(empty)* | Empty = first model listed by `/models` |
| `LLM_MAX_CONTEXT` | `0` | Context window for the gauge; 0 = `max_model_len` from `/models` |
| `LLM_MAX_TOKENS` | `4096` | Max output tokens per model reply (reasoning included) |
| `LLM_MAX_ROUNDS` | `10` | Max model requests per user turn (loop guard) |
| `LLM_API_KEY` | *(empty)* | Sent as `Bearer` token if set; never shown in the UI |
| `INSPECTOR_HOST` / `INSPECTOR_PORT` | `127.0.0.1` / `8090` | Where the UI listens |

The harness system prompt is editable in the same panel; server instructions are appended to it automatically.

## Demo script (~8 minutes)

1. **No MCP.** Click *What is the price of cola at Prix Malin?* → the model invents a price. *"It has no data — and doesn't know it."*
2. **Add Prix Malin** (chip, then **Add**). Walk through the discovery cards: `initialize`, `tools/list`, `resources/list`, `prompts/list`, then *"3 tool definitions added to the model context"*. Open the right panel: same question, but now the request carries tool definitions.
3. **Ask again.** Follow the loop: *Request #1 → model asks for a tool call → harness calls MCP → result added as a `tool` message → Request #2 re-sends everything*. Open *Exact JSON body* to show it.
4. **Add HyperMax**, ask *Compare the price of cola at Prix Malin and HyperMax.* Point at the token gauge: more servers = more context used on every request.
5. **New conversation.** History is empty, servers remain: the model "forgets" because it never remembered.
6. **Add BricoPro, attach `bricopro://guides/compatibilite`** (Attach), then **Use** `choose_barbecue_setup` (10 · 120 · charbon). Show that both arrive as *user* messages, selected by you, not by the model.

Small models make visible mistakes (wrong arguments, swapped references, unused tools). Keep them: errors are returned to the model as `tool` messages, which shows how an agent recovers — or doesn't.

## Model notes

- Default endpoint serves `qwen3-coder` (Qwen3.6-35B-A3B, AWQ 4-bit, 131k context): reliable tool calls, parallel calls across servers, reasoning returned in a separate `reasoning` field. A turn takes a few seconds per model request.
- Earlier tests with `Qwen3-0.6B` (4k context) worked mechanically but gave unreliable answers; three servers already use ~1,600 tokens of tool definitions per request, so keep **≥ 16k context** for the capstone.
- vLLM needs `--enable-auto-tool-choice --tool-call-parser hermes` for tool calls; `--reasoning-parser qwen3` moves the `<think>` text out of `content` (the inspector handles both).
- The harness drops the model's reasoning from the history and stores tool results as compact JSON to save context.

## Tests

`pytest -q` covers the harness and the web API with canned model responses (no network). `pytest -m live` runs one real round trip against `LLM_BASE_URL` with the MCP servers running.
