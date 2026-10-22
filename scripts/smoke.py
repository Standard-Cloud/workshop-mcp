"""Check the 3 running MCP servers over real HTTP: discovery counts and one tool call each."""
import json

import anyio
from mcp import Client

SERVERS = {
    "prix-malin": ("http://localhost:9001/mcp", (3, 1, 2), "list_current_arrivals", {}),
    "hypermax": ("http://localhost:9002/mcp", (3, 1, 1), "search_catalog", {"query": "cola"}),
    "bricopro": ("http://localhost:9003/mcp", (3, 2, 1), "get_equipment_specs", {"reference": "BP-101"}),
}


async def check(name, url, expected, tool, args):
    async with Client(url) as c:
        counts = (
            len((await c.list_tools()).tools),
            len((await c.list_resources()).resources),
            len((await c.list_prompts()).prompts),
        )
        result = await c.call_tool(tool, args)
    assert counts == expected, f"{name}: got {counts}, expected {expected}"
    assert not result.is_error, result.content[0].text
    preview = json.dumps(json.loads(result.content[0].text), ensure_ascii=False)[:100]
    print(f"OK {name:<11} tools/resources/prompts={counts}  {tool} -> {preview}...")
    return counts


async def main():
    totals = [await check(name, *spec) for name, spec in SERVERS.items()]
    print("TOTAL tools/resources/prompts =", tuple(map(sum, zip(*totals))))


anyio.run(main)
