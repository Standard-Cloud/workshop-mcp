import pytest
from mcp import Client

from conftest import mcp_server, result_json

pytestmark = pytest.mark.anyio


@pytest.fixture
def server(monkeypatch):
    return mcp_server("bricopro", monkeypatch)


async def call(server, tool, **args):
    async with Client(server) as c:
        return await c.call_tool(tool, args)


def refs(data):
    return [p["reference"] for p in data["products"]]


async def test_discovery_exposes_3_tools_2_resources_1_prompt(server):
    async with Client(server) as c:
        tools = (await c.list_tools()).tools
        assert sorted(t.name for t in tools) == [
            "check_accessory_compatibility",
            "find_barbecue_equipment",
            "get_equipment_specs",
        ]
        assert all(t.annotations.read_only_hint for t in tools)
        assert sorted(r.uri for r in (await c.list_resources()).resources) == [
            "bricopro://guides/barbecue",
            "bricopro://guides/compatibilite",
        ]
        assert [p.name for p in (await c.list_prompts()).prompts] == ["choose_barbecue_setup"]


async def test_find_equipment_without_filters_returns_all_9(server):
    data = result_json(await call(server, "find_barbecue_equipment"))
    assert data["merchant"] == "BricoPro"
    assert data["count"] == 9


@pytest.mark.parametrize(
    "args, expected",
    [
        ({"category": "barbecues"}, ["BP-100", "BP-101", "BP-102"]),
        ({"fuel_type": "gaz"}, ["BP-102"]),
        ({"category": "barbecues", "fuel_type": "charbon"}, ["BP-100", "BP-101"]),
        ({"max_price_eur": 5}, ["BP-105"]),
        ({"category": "barbecues", "in_stock_only": True, "max_price_eur": 100}, ["BP-100", "BP-101"]),
    ],
)
async def test_find_equipment_filters(server, args, expected):
    assert refs(result_json(await call(server, "find_barbecue_equipment", **args))) == expected


async def test_specs_are_normalized_and_keep_technical_fields(server):
    data = result_json(await call(server, "get_equipment_specs", reference="BP-101"))
    assert data == {
        "merchant": "BricoPro",
        "reference": "BP-101",
        "name": "Barbecue charbon familial",
        "category": "barbecues",
        "pack": {"value": 1, "measure": "pièce"},
        "price_eur": 89.9,
        "in_stock": True,
        "stock_packs": 5,
        "manufacturer_model": "BBQ-F200",
        "fuel_type": "charbon",
        "capacity_people": {"min": 8, "max": 12},
    }


async def test_specs_unknown_reference(server):
    assert (await call(server, "get_equipment_specs", reference="BP-999")).is_error


@pytest.mark.parametrize(
    "bbq, accessory, compatible",
    [
        ("BP-101", "BP-103", True),
        ("BP-102", "BP-103", False),
        ("BP-102", "BP-106", True),
        ("BP-101", "BP-100", None),
    ],
)
async def test_compatibility(server, bbq, accessory, compatible):
    data = result_json(
        await call(server, "check_accessory_compatibility", barbecue_reference=bbq, accessory_reference=accessory)
    )
    assert data["compatible"] is compatible
    assert data["barbecue_reference"] == bbq
    assert data["accessory_reference"] == accessory
    assert data["reason"]


@pytest.mark.parametrize("bbq, accessory", [("BP-999", "BP-103"), ("BP-103", "BP-105")])
async def test_compatibility_errors(server, bbq, accessory):
    result = await call(server, "check_accessory_compatibility", barbecue_reference=bbq, accessory_reference=accessory)
    assert result.is_error


async def test_two_guides(server):
    async with Client(server) as c:
        guide = (await c.read_resource("bricopro://guides/barbecue")).contents[0].text
        compat = (await c.read_resource("bricopro://guides/compatibilite")).contents[0].text
    assert "BBQ-F200" in guide and "8 to 12" in guide
    assert "BBQ-G300" in compat and "BP-106" in compat


async def test_prompt_fills_arguments(server):
    async with Client(server) as c:
        prompt = await c.get_prompt("choose_barbecue_setup", {"guests": "10", "budget_eur": "120"})
    text = prompt.messages[0].content.text
    assert "10 guests" in text and "120 EUR" in text and "no preference" in text


async def test_category_and_fuel_are_enums(server):
    async with Client(server) as c:
        tool = next(t for t in (await c.list_tools()).tools if t.name == "find_barbecue_equipment")
        invalid = await c.call_tool("find_barbecue_equipment", {"category": "grills"})
    props = tool.input_schema["properties"]
    assert sorted(props["category"]["anyOf"][0]["enum"]) == ["accessoires", "allumage", "barbecues", "combustibles"]
    assert sorted(props["fuel_type"]["anyOf"][0]["enum"]) == ["charbon", "gaz"]
    assert invalid.is_error
