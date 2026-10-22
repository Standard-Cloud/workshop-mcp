"""Prix Malin MCP server — adapts the Prix Malin REST API for AI agents."""
import os
import re
from typing import Literal

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import BaseModel

API_URL = os.environ.get("PRIX_MALIN_API_URL", "http://localhost:8001")
MERCHANT = "Prix Malin"
Family = Literal["viande", "surgelé", "boulangerie", "épicerie", "boisson"]
READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)

mcp = MCPServer(
    "prix-malin",
    instructions=(
        "Prix Malin is a discount food store open 09:00-17:00 (Europe/Paris). "
        "Read-only: these tools never reserve or buy anything. Stock is counted in whole packs."
    ),
)


def api_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=API_URL)


async def api_get(path: str, params: dict | None = None) -> httpx.Response:
    async with api_client() as client:
        return await client.get(path, params=params)


def to_eur(cents: int) -> float:
    return round(cents / 100, 2)


def normalize(a: dict) -> dict:
    return {
        "merchant": MERCHANT,
        "arrival_code": a["code_arrivage"],
        "name": a["libelle"],
        "family": a["famille"],
        "pack": {"quantity": a["conditionnement"]["quantite"], "unit": a["conditionnement"]["unite"]},
        "price_eur": to_eur(a["prix_centimes_ttc"]),
        "stock_packs": a["lots_disponibles"],
        "status": a["etat"],
    }


def parse_time(value: str) -> str:
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value):
        raise ToolError(f"Invalid shopping_time '{value}': expected HH:mm, e.g. 16:30.")
    return value


@mcp.tool(annotations=READ_ONLY)
async def list_current_arrivals(family: Family | None = None, available_only: bool = False) -> dict:
    """List Prix Malin arrivals (products) with EUR prices, pack size and stock in packs.

    family: merchant product family (viande = meat, surgelé = frozen, boulangerie = bakery,
    épicerie = grocery, boisson = drinks).
    available_only: true to hide sold-out arrivals. By default sold-out items are included.
    """
    params = {}
    if family:
        params["famille"] = family
    if available_only:
        params["disponible"] = "true"
    arrivals = [normalize(a) for a in (await api_get("/magasin/arrivages", params)).json()["arrivages"]]
    return {"merchant": MERCHANT, "currency": "EUR", "count": len(arrivals), "arrivals": arrivals}


@mcp.tool(annotations=READ_ONLY)
async def get_arrival_details(arrival_code: str) -> dict:
    """Get one Prix Malin arrival by its code (e.g. PM-001)."""
    r = await api_get(f"/magasin/arrivages/{arrival_code}")
    if r.status_code == 404:
        raise ToolError(f"Unknown arrival code '{arrival_code}': Prix Malin does not list this product.")
    return normalize(r.json())


class PurchaseLine(BaseModel):
    arrival_code: str
    packs: int


@mcp.tool(annotations=READ_ONLY)
async def check_purchase_feasibility(items: list[PurchaseLine], shopping_time: str) -> dict:
    """Check whether a list of packs can be bought at Prix Malin at a given time (HH:mm, Europe/Paris).

    packs = number of whole packs, not individual pieces. This is a simulation:
    nothing is reserved and stock is not decremented.
    """
    parse_time(shopping_time)
    requested: dict[str, int] = {}
    for item in items:
        if item.packs <= 0:
            raise ToolError(f"packs must be a positive integer (got {item.packs} for {item.arrival_code}).")
        requested[item.arrival_code] = requested.get(item.arrival_code, 0) + item.packs

    hours = (await api_get("/magasin/infos")).json()["horaires"]
    opens_at, closes_at = hours.split("-")
    store_open = opens_at <= shopping_time < closes_at
    stock = {a["code_arrivage"]: a for a in (await api_get("/magasin/arrivages")).json()["arrivages"]}

    lines = []
    for code, packs in requested.items():
        arrival = stock.get(code)
        if arrival is None:
            lines.append({"arrival_code": code, "requested_packs": packs, "status": "not_found"})
            continue
        available = arrival["lots_disponibles"]
        fulfillable = min(packs, available) if store_open else 0
        if available == 0:
            status = "out_of_stock"
        elif packs > available:
            status = "partial"
        else:
            status = "ok"
        price = to_eur(arrival["prix_centimes_ttc"])
        lines.append({
            "arrival_code": code,
            "name": arrival["libelle"],
            "requested_packs": packs,
            "available_packs": available,
            "fulfillable_packs": fulfillable,
            "unit_price_eur": price,
            "line_total_eur": round(fulfillable * price, 2),
            "status": status,
        })

    if not store_open:
        overall = "store_closed"
    elif all(line["status"] == "ok" for line in lines):
        overall = "feasible"
    else:
        overall = "partially_feasible"
    return {
        "merchant": MERCHANT,
        "shopping_time": shopping_time,
        "time_zone": "Europe/Paris",
        "opening_hours": hours,
        "store_open": store_open,
        "status": overall,
        "lines": lines,
        "total_eur": round(sum(line.get("line_total_eur", 0) for line in lines), 2),
        "currency": "EUR",
        "note": "Simulation only: no stock is reserved.",
    }


@mcp.resource("prixmalin://store/policy", name="store_policy", title="Prix Malin — arrivals policy and opening hours",
              mime_type="text/markdown")
def store_policy() -> str:
    return (
        "# Prix Malin — arrivals policy\n\n"
        "Prix Malin is open every day from **09:00 to 17:00** (Europe/Paris). "
        "The assortment is limited and depends on arrivals; some listed products are sold out. "
        "**No organic meat, no chips and no barbecue equipment** are sold. "
        "Quantities are whole packs. No stock is reserved; any availability estimate is indicative. "
        "Public holidays are ignored for this exercise.\n"
    )


@mcp.prompt(title="Lowest-cost meal at Prix Malin")
def find_lowest_cost_meal(guests: int, budget_eur: float, shopping_time: str) -> str:
    """Plan the cheapest food shopping at Prix Malin for a group."""
    return (
        f"Prepare the cheapest possible food shopping at Prix Malin for {guests} guests, "
        f"with a maximum budget of {budget_eur:g} EUR and a store visit at {shopping_time}. "
        "Check the arrivals and their availability, respect whole packs and verify feasibility with the tools. "
        "Show quantities, prices, total cost and any needs that are not covered. "
        "Never claim the merchant sells items it does not list."
    )


@mcp.prompt(title="Adapt my list to Prix Malin arrivals")
def adapt_to_arrivals(requested_items: str, shopping_time: str) -> str:
    """Match a free-text shopping list against what Prix Malin actually has."""
    return (
        f"Here is what I need: {requested_items}. For a visit to Prix Malin at {shopping_time}, "
        "use the merchant tools to identify items in stock, sold-out items and items not in the catalog. "
        "Suggest substitutions only among products actually offered, and clearly distinguish substitution, "
        "out of stock and structurally unavailable. List what must be bought from another merchant, "
        "without assuming you have access to it."
    )


if __name__ == "__main__":
    mcp.run("streamable-http", host="0.0.0.0", port=int(os.environ.get("PORT", "9001")),
            stateless_http=True, json_response=True)
