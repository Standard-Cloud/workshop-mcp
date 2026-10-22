"""MCP Agent Inspector — instructor demo UI over the narrated harness."""
import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))
from harness import Harness, Settings  # noqa: E402

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="MCP Agent Inspector")
harness = Harness(Settings.from_env())


def stream(events) -> StreamingResponse:
    async def lines():
        async for e in events:
            yield json.dumps(e, ensure_ascii=False) + "\n"

    return StreamingResponse(lines(), media_type="application/x-ndjson")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/state")
async def state():
    try:
        model = await harness.model_info()
    except Exception as exc:
        model = {"error": f"{type(exc).__name__}: {exc}"}
    return {
        "settings": harness.settings.public(),
        "model": model,
        "servers": [
            {"name": s.name, "url": s.url, "tools": s.tools, "resources": s.resources, "prompts": s.prompts}
            for s in harness.servers.values()
        ],
        "history": harness.history,
        "system_prompt": harness.system_prompt(),
        "tool_definitions": harness.tool_definitions(),
    }


class SettingsUpdate(BaseModel):
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    max_context: int | None = None
    max_tokens: int | None = None
    max_rounds: int | None = None
    system_prompt: str | None = None


@app.post("/api/settings")
def update_settings(update: SettingsUpdate):
    for key, value in update.model_dump(exclude_none=True).items():
        setattr(harness.settings, key, value)
    return harness.settings.public()


class AddServer(BaseModel):
    url: str


@app.post("/api/servers")
def add_server(body: AddServer):
    return stream(harness.add_server(body.url))


@app.delete("/api/servers/{name}")
def remove_server(name: str):
    harness.remove_server(name)
    return {"removed": name}


class Chat(BaseModel):
    message: str


@app.post("/api/chat")
def chat(body: Chat):
    return stream(harness.chat(body.message))


class AttachResource(BaseModel):
    server: str
    uri: str


@app.post("/api/resources/attach")
def attach_resource(body: AttachResource):
    return stream(harness.attach_resource(body.server, body.uri))


class UsePrompt(BaseModel):
    server: str
    name: str
    arguments: dict[str, str] = {}


@app.post("/api/prompts/use")
def use_prompt(body: UsePrompt):
    return stream(harness.use_prompt(body.server, body.name, body.arguments))


@app.post("/api/reset")
def reset():
    harness.reset()
    return {"history": []}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.environ.get("INSPECTOR_HOST", "127.0.0.1"), port=int(os.environ.get("INSPECTOR_PORT", "8090")))
