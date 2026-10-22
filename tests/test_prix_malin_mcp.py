import pytest
from mcp import Client

from conftest import mcp_server, result_json

pytestmark = pytest.mark.anyio


@pytest.fixture
def server(monkeypatch):
    return mcp_server("prix-malin", monkeypatch)


async def test_discovery_exposes_3_tools_1_resource_2_prompts(server):
    async with Client(server) as c:
        tools = (await c.list_tools()).tools
        assert sorted(t.name for t in tools) == [
            "check_purchase_feasibility",
            "get_arrival_details",
            "list_current_arrivals",
        ]
        assert all(t.annotations.read_only_hint for t in tools)
        assert [r.uri for r in (await c.list_resources()).resources] == ["prixmalin://store/policy"]
        assert sorted(p.name for p in (await c.list_prompts()).prompts) == [
            "adapt_to_arrivals",
            "find_lowest_cost_meal",
        ]


async def test_list_arrivals_converts_cents_to_eur(server):
    async with Client(server) as c:
        data = result_json(await c.call_tool("list_current_arrivals", {}))
    assert data["merchant"] == "Prix Malin"
    assert data["currency"] == "EUR"
    assert data["count"] == 9
    sausages = data["arrivals"][0]
    assert sausages == {
        "merchant": "Prix Malin",
        "arrival_code": "PM-001",
        "name": "Saucisses de porc x6",
        "family": "viande",
        "pack": {"quantity": 6, "unit": "pièce"},
        "price_eur": 4.5,
        "stock_packs": 12,
        "status": "en_stock",
    }


async def test_list_arrivals_filters(server):
    async with Client(server) as c:
        data = result_json(await c.call_tool("list_current_arrivals", {"family": "viande", "available_only": True}))
    assert [a["arrival_code"] for a in data["arrivals"]] == ["PM-001", "PM-002", "PM-003"]


async def test_arrival_details_and_unknown_code(server):
    async with Client(server) as c:
        skewers = result_json(await c.call_tool("get_arrival_details", {"arrival_code": "PM-004"}))
        unknown = await c.call_tool("get_arrival_details", {"arrival_code": "CHIPS"})
    assert skewers["stock_packs"] == 0
    assert skewers["price_eur"] == 6.9
    assert unknown.is_error
    assert "CHIPS" in unknown.content[0].text


async def test_feasibility_line_statuses_and_total(server):
    items = [
        {"arrival_code": "PM-001", "packs": 2},
        {"arrival_code": "PM-004", "packs": 3},
        {"arrival_code": "PM-007", "packs": 10},
        {"arrival_code": "CHIPS", "packs": 1},
    ]
    async with Client(server) as c:
        data = result_json(await c.call_tool("check_purchase_feasibility", {"items": items, "shopping_time": "16:30"}))
    assert data["store_open"] is True
    assert data["status"] == "partially_feasible"
    lines = {line["arrival_code"]: line for line in data["lines"]}
    assert lines["PM-001"] == {
        "arrival_code": "PM-001",
        "name": "Saucisses de porc x6",
        "requested_packs": 2,
        "available_packs": 12,
        "fulfillable_packs": 2,
        "unit_price_eur": 4.5,
        "line_total_eur": 9.0,
        "status": "ok",
    }
    assert lines["PM-004"]["status"] == "out_of_stock"
    assert lines["PM-004"]["fulfillable_packs"] == 0
    assert lines["PM-007"]["status"] == "partial"
    assert lines["PM-007"]["fulfillable_packs"] == 7
    assert lines["PM-007"]["line_total_eur"] == 8.4
    assert lines["CHIPS"]["status"] == "not_found"
    assert data["total_eur"] == 17.4


async def test_feasibility_merges_duplicate_lines(server):
    items = [{"arrival_code": "PM-005", "packs": 1}, {"arrival_code": "PM-005", "packs": 2}]
    async with Client(server) as c:
        data = result_json(await c.call_tool("check_purchase_feasibility", {"items": items, "shopping_time": "10:00"}))
    assert len(data["lines"]) == 1
    assert data["lines"][0]["requested_packs"] == 3
    assert data["status"] == "feasible"
    assert data["total_eur"] == 5.4


@pytest.mark.parametrize("time", ["08:59", "17:00", "18:30"])
async def test_feasibility_store_closed(server, time):
    items = [{"arrival_code": "PM-001", "packs": 1}]
    async with Client(server) as c:
        data = result_json(await c.call_tool("check_purchase_feasibility", {"items": items, "shopping_time": time}))
    assert data["store_open"] is False
    assert data["status"] == "store_closed"
    assert data["lines"][0]["fulfillable_packs"] == 0
    assert data["total_eur"] == 0


@pytest.mark.parametrize(
    "items, time",
    [
        ([{"arrival_code": "PM-001", "packs": 0}], "16:30"),
        ([{"arrival_code": "PM-001", "packs": -2}], "16:30"),
        ([{"arrival_code": "PM-001", "packs": 1}], "4pm"),
    ],
)
async def test_feasibility_rejects_invalid_input(server, items, time):
    async with Client(server) as c:
        result = await c.call_tool("check_purchase_feasibility", {"items": items, "shopping_time": time})
    assert result.is_error


async def test_policy_resource(server):
    async with Client(server) as c:
        text = (await c.read_resource("prixmalin://store/policy")).contents[0].text
    assert "09:00 to 17:00" in text
    assert "no chips" in text.lower()


async def test_prompts_fill_arguments(server):
    async with Client(server) as c:
        meal = await c.get_prompt("find_lowest_cost_meal", {"guests": "10", "budget_eur": "40", "shopping_time": "16:30"})
        adapt = await c.get_prompt(
            "adapt_to_arrivals", {"requested_items": "chicken skewers, fries, chips", "shopping_time": "16:30"}
        )
    meal_text = meal.messages[0].content.text
    assert "10 guests" in meal_text and "40 EUR" in meal_text and "16:30" in meal_text
    assert "chicken skewers, fries, chips" in adapt.messages[0].content.text


async def test_family_is_an_enum_of_merchant_families(server):
    async with Client(server) as c:
        tool = next(t for t in (await c.list_tools()).tools if t.name == "list_current_arrivals")
        invalid = await c.call_tool("list_current_arrivals", {"family": "colas"})
    assert sorted(tool.input_schema["properties"]["family"]["anyOf"][0]["enum"]) == sorted(
        ["viande", "surgelé", "boulangerie", "épicerie", "boisson"]
    )
    assert invalid.is_error
