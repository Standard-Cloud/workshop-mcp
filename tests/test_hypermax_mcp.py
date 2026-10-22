import pytest
from mcp import Client

from conftest import mcp_server, result_json

pytestmark = pytest.mark.anyio


@pytest.fixture
def server(monkeypatch):
    return mcp_server("hypermax", monkeypatch)


async def search(server, **args):
    async with Client(server) as c:
        return result_json(await c.call_tool("search_catalog", args))


def skus(data):
    return [p["sku"] for p in data["products"]]


async def test_discovery_exposes_3_tools_1_resource_1_prompt(server):
    async with Client(server) as c:
        tools = (await c.list_tools()).tools
        assert sorted(t.name for t in tools) == ["get_product_information", "get_store_opening_status", "search_catalog"]
        assert all(t.annotations.read_only_hint for t in tools)
        assert [r.uri for r in (await c.list_resources()).resources] == ["hypermax://catalog/categories"]
        assert [p.name for p in (await c.list_prompts()).prompts] == ["prepare_organic_barbecue"]


async def test_search_without_filters_returns_all_17(server):
    data = await search(server)
    assert data["merchant"] == "HyperMax"
    assert data["count"] == 17


async def test_search_normalizes_products(server):
    data = await search(server, query="BARBECUE CHARBON")
    assert data["products"] == [
        {
            "merchant": "HyperMax",
            "sku": "HMX-014",
            "name": "Barbecue charbon compact",
            "department": "plein_air",
            "pack": {"count": 1, "unit": "pièce"},
            "price_eur": 49.9,
            "stock_packs": 5,
            "organic": False,
            "manufacturer_model": "BBQ-C100",
        }
    ]


@pytest.mark.parametrize(
    "args, expected",
    [
        ({"organic_only": True}, ["HMX-005", "HMX-006"]),
        ({"query": "cola"}, ["HMX-011"]),
        ({"department": "boissons", "max_price_eur": 1.0}, ["HMX-012"]),
        ({"query": "saucisses", "organic_only": True}, ["HMX-005"]),
        ({"query": "caviar"}, []),
    ],
)
async def test_search_filters(server, args, expected):
    assert skus(await search(server, **args)) == expected


async def test_in_stock_only_keeps_everything_with_stock(server):
    assert (await search(server, in_stock_only=True))["count"] == 17


async def test_product_information(server):
    async with Client(server) as c:
        cola = result_json(await c.call_tool("get_product_information", {"sku": "HMX-011"}))
        unknown = await c.call_tool("get_product_information", {"sku": "HMX-999"})
    assert cola["price_eur"] == 1.15
    assert unknown.is_error


@pytest.mark.parametrize(
    "time, is_open, next_opening",
    [
        ("16:30", True, None),
        ("18:30", True, None),
        ("08:00", True, None),
        ("07:15", False, {"day": "same_day", "time": "08:00"}),
        ("21:00", False, {"day": "next_day", "time": "08:00"}),
    ],
)
async def test_opening_status(server, time, is_open, next_opening):
    async with Client(server) as c:
        data = result_json(await c.call_tool("get_store_opening_status", {"shopping_time": time}))
    assert data == {
        "merchant": "HyperMax",
        "shopping_time": time,
        "time_zone": "Europe/Paris",
        "is_open": is_open,
        "opens_at": "08:00",
        "closes_at": "21:00",
        "next_opening": next_opening,
    }


async def test_opening_status_rejects_bad_time(server):
    async with Client(server) as c:
        assert (await c.call_tool("get_store_opening_status", {"shopping_time": "25:99"})).is_error


async def test_categories_resource(server):
    async with Client(server) as c:
        text = (await c.read_resource("hypermax://catalog/categories")).contents[0].text
    assert "HMX-005" in text and "HMX-006" in text and "08:00 to 21:00" in text


async def test_prompt_fills_arguments(server):
    async with Client(server) as c:
        prompt = await c.get_prompt(
            "prepare_organic_barbecue", {"guests": "6", "budget_eur": "60", "shopping_time": "18:30"}
        )
    text = prompt.messages[0].content.text
    assert "6 guests" in text and "60 EUR" in text and "18:30" in text


async def test_department_is_an_enum(server):
    async with Client(server) as c:
        tool = next(t for t in (await c.list_tools()).tools if t.name == "search_catalog")
        invalid = await c.call_tool("search_catalog", {"department": "bakery"})
    assert sorted(tool.input_schema["properties"]["department"]["anyOf"][0]["enum"]) == sorted(
        ["boucherie", "épicerie", "surgelés", "boulangerie", "boissons", "traiteur", "plein_air"]
    )
    assert invalid.is_error
