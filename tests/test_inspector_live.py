"""One real round trip: running MCP servers + the configured model. Run with `pytest -m live`."""
import pytest

from conftest import load

pytestmark = [pytest.mark.live, pytest.mark.anyio]
harness_mod = load("agent-inspector", "harness")


async def test_real_model_calls_a_bricopro_tool():
    h = harness_mod.Harness(harness_mod.Settings.from_env())
    discovery = [e async for e in h.add_server("http://localhost:9003/mcp")]
    assert discovery[-1]["type"] == "context_change"
    events = [e async for e in h.chat("Is the charcoal BP-103 compatible with the barbecue BP-102?")]
    print(*(f"{e['type']}: {e['title']} | {e['summary'][:120]}" for e in events), sep="\n")
    assert "mcp_call" in [e["type"] for e in events]
    assert events[-1]["type"] == "final_answer"
