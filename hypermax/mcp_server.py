"""HyperMax MCP server — adapts the HyperMax REST API for AI agents."""
import os
import re
from typing import Literal

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

API_URL = os.environ.get("HYPERMAX_API_URL", "http://localhost:8002")
STORE_ID = "HMX-001"
MERCHANT = "HyperMax"
Department = Literal["boucherie", "épicerie", "surgelés", "boulangerie", "boissons", "traiteur", "plein_air"]
READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)

mcp = MCPServer(
    "hypermax",
    instructions=(
        "HyperMax is a general hypermarket open 08:00-21:00 (Europe/Paris), the only merchant selling organic meat. "
        "Read-only: these tools never reserve or buy anything. Stock is counted in packs."
    ),
)


def api_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=API_URL)


async def api_get(path: str, params: dict | None = None) -> httpx.Response:
    async with api_client() as client:
        return await client.get(path, params=params)


def normalize(p: dict) -> dict:
    product = {
        "merchant": MERCHANT,
        "sku": p["sku"],
        "name": p["title"],
        "department": p["department"],
        "pack": p["pack"],
        "price_eur": p["priceTtc"],
        "stock_packs": p["inventoryUnits"],
        "organic": p["isOrganic"],
    }
    if "manufacturerModel" in p:
        product["manufacturer_model"] = p["manufacturerModel"]
    return product


@mcp.tool(annotations=READ_ONLY)
async def search_catalog(
    query: str | None = None,
    department: Department | None = None,
    organic_only: bool = False,
    max_price_eur: float | None = None,
    in_stock_only: bool = False,
) -> dict:
    """Search the HyperMax catalog (food and barbecue equipment). All filters are optional and combined.

    query: case-insensitive text match on the product title (French titles, e.g. "saucisses", "cola").
    department: boucherie = butcher, épicerie = grocery, surgelés = frozen, boulangerie = bakery,
    boissons = drinks, traiteur = deli, plein_air = barbecue equipment.
    organic_only: true keeps only products flagged organic by the merchant.
    """
    params = {}
    if department:
        params["department"] = department
    if organic_only:
        params["organic"] = "true"
    products = [normalize(p) for p in (await api_get("/api/v1/catalog/products", params)).json()["items"]]
    if query:
        products = [p for p in products if query.lower() in p["name"].lower()]
    if max_price_eur is not None:
        products = [p for p in products if p["price_eur"] <= max_price_eur]
    if in_stock_only:
        products = [p for p in products if p["stock_packs"] > 0]
    return {"merchant": MERCHANT, "currency": "EUR", "count": len(products), "products": products}


@mcp.tool(annotations=READ_ONLY)
async def get_product_information(sku: str) -> dict:
    """Get one HyperMax product by SKU (e.g. HMX-005)."""
    r = await api_get(f"/api/v1/catalog/products/{sku}")
    if r.status_code == 404:
        raise ToolError(f"Unknown SKU '{sku}': HyperMax does not list this product.")
    return normalize(r.json())


@mcp.tool(annotations=READ_ONLY)
async def get_store_opening_status(shopping_time: str) -> dict:
    """Tell whether HyperMax is open at a given local time (HH:mm, Europe/Paris), same hours every day."""
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", shopping_time):
        raise ToolError(f"Invalid shopping_time '{shopping_time}': expected HH:mm, e.g. 16:30.")
    hours = (await api_get(f"/api/v1/stores/{STORE_ID}")).json()["businessHours"]
    opens_at, closes_at = hours["opensAt"], hours["closesAt"]
    is_open = opens_at <= shopping_time < closes_at
    next_opening = None
    if not is_open:
        next_opening = {"day": "same_day" if shopping_time < opens_at else "next_day", "time": opens_at}
    return {
        "merchant": MERCHANT,
        "shopping_time": shopping_time,
        "time_zone": hours["timeZone"],
        "is_open": is_open,
        "opens_at": opens_at,
        "closes_at": closes_at,
        "next_opening": next_opening,
    }


@mcp.resource("hypermax://catalog/categories", name="catalog_categories",
              title="HyperMax — departments and organic scope", mime_type="text/markdown")
def catalog_categories() -> str:
    return (
        "# HyperMax — departments and organic scope\n\n"
        "Catalog departments: `boucherie`, `épicerie`, `surgelés`, `boulangerie`, `boissons`, `traiteur`, "
        "`plein_air`. The organic filter uses the `isOrganic` attribute, not the product name. "
        "In this scenario **only two meat products are organic** (`HMX-005`, `HMX-006`). "
        "HyperMax is open from **08:00 to 21:00** every day (Europe/Paris). "
        "The store sells both food and barbecue equipment.\n"
    )


@mcp.prompt(title="Organic barbecue at HyperMax")
def prepare_organic_barbecue(guests: int, budget_eur: float, shopping_time: str) -> str:
    """Plan a barbecue with organic-only meat from HyperMax."""
    return (
        f"Organise a barbecue for {guests} guests with organic-only meat and a maximum budget of {budget_eur:g} EUR. "
        "Search only meat flagged organic in the HyperMax catalog; complete if useful with sides, drinks or "
        f"equipment from the same merchant. Check stock and that the store is open at {shopping_time}. "
        "Show packs, total price and any constraints or missing items. "
        "Never call meat organic when its `organic` attribute is false."
    )


if __name__ == "__main__":
    mcp.run("streamable-http", host="0.0.0.0", port=int(os.environ.get("PORT", "9002")),
            stateless_http=True, json_response=True)
