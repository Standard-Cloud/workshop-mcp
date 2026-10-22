"""BricoPro MCP server — adapts the BricoPro REST API for AI agents."""
import os
from typing import Literal

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

API_URL = os.environ.get("BRICOPRO_API_URL", "http://localhost:8003")
MERCHANT = "BricoPro"
Category = Literal["barbecues", "combustibles", "allumage", "accessoires"]
Fuel = Literal["charbon", "gaz"]
READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)

mcp = MCPServer(
    "bricopro",
    instructions=(
        "BricoPro is a DIY store open 07:00-19:00 (Europe/Paris) selling barbecues, fuel and accessories. "
        "It sells no food. Read-only: these tools never reserve or buy anything."
    ),
)


def api_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=API_URL)


async def api_get(path: str, params: dict | None = None) -> httpx.Response:
    async with api_client() as client:
        return await client.get(path, params=params)


OPTIONAL_FIELDS = {
    "modele_fabricant": "manufacturer_model",
    "type_combustible": "fuel_type",
    "combustible_requis": "required_fuel",
    "capacite_personnes": "capacity_people",
    "modeles_compatibles": "compatible_models",
}


def normalize(r: dict) -> dict:
    product = {
        "merchant": MERCHANT,
        "reference": r["reference"],
        "name": r["designation"],
        "category": r["rayon"],
        "pack": {"value": r["contenu"]["valeur"], "measure": r["contenu"]["mesure"]},
        "price_eur": round(r["tarif"]["montant_ttc_centimes"] / 100, 2),
        "in_stock": r["disponibilite"]["en_stock"],
        "stock_packs": r["disponibilite"]["quantite_cond"],
    }
    product.update({new: r[old] for old, new in OPTIONAL_FIELDS.items() if old in r})
    return product


async def fetch(reference: str) -> dict:
    r = await api_get(f"/pro/references/{reference}")
    if r.status_code == 404:
        raise ToolError(f"Unknown reference '{reference}': BricoPro does not list this product.")
    return r.json()


@mcp.tool(annotations=READ_ONLY)
async def find_barbecue_equipment(
    category: Category | None = None,
    fuel_type: Fuel | None = None,
    max_price_eur: float | None = None,
    in_stock_only: bool = False,
) -> dict:
    """Find BricoPro barbecues, fuel and accessories. All filters are optional and combined.

    category: barbecues, combustibles = fuel, allumage = firelighters, accessoires = accessories.
    fuel_type: "charbon" (charcoal) or "gaz" (gas); matches the barbecue fuel or the fuel a consumable is for.
    """
    params = {}
    if category:
        params["rayon"] = category
    if in_stock_only:
        params["en_stock"] = "true"
    products = [normalize(r) for r in (await api_get("/pro/references", params)).json()["references"]]
    if fuel_type:
        products = [p for p in products if fuel_type in (p.get("fuel_type"), p.get("required_fuel"))]
    if max_price_eur is not None:
        products = [p for p in products if p["price_eur"] <= max_price_eur]
    return {"merchant": MERCHANT, "currency": "EUR", "count": len(products), "products": products}


@mcp.tool(annotations=READ_ONLY)
async def get_equipment_specs(reference: str) -> dict:
    """Get the technical sheet of one BricoPro reference (e.g. BP-101): model, fuel, capacity, compatibility."""
    return normalize(await fetch(reference))


@mcp.tool(annotations=READ_ONLY)
async def check_accessory_compatibility(barbecue_reference: str, accessory_reference: str) -> dict:
    """Check documented compatibility between a BricoPro barbecue and an accessory or fuel.

    compatible=true: documented compatible. false: documented incompatible.
    null: no compatibility data, cannot be verified (do not assume).
    """
    barbecue = await fetch(barbecue_reference)
    accessory = await fetch(accessory_reference)
    model = barbecue.get("modele_fabricant")
    if model is None:
        raise ToolError(f"'{barbecue_reference}' is not a barbecue (no manufacturer model).")
    models = accessory.get("modeles_compatibles")
    if models is None:
        compatible, reason = None, f"{accessory_reference} has no documented compatibility list: cannot verify."
    elif model in models:
        compatible, reason = True, f"{accessory_reference} documents compatibility with {model}."
    else:
        compatible, reason = False, f"{accessory_reference} is documented for {', '.join(models)} only, not {model}."
    return {
        "merchant": MERCHANT,
        "barbecue_reference": barbecue_reference,
        "barbecue_model": model,
        "accessory_reference": accessory_reference,
        "compatible": compatible,
        "reason": reason,
    }


@mcp.resource("bricopro://guides/barbecue", name="barbecue_guide", title="BricoPro — choosing a barbecue",
              mime_type="text/markdown")
def barbecue_guide() -> str:
    return (
        "# BricoPro — choosing a barbecue\n\n"
        "**Models offered:** compact charcoal barbecue (`BP-100`, `BBQ-C100`, indicative capacity 4 to 6 people); "
        "family charcoal barbecue (`BP-101`, `BBQ-F200`, indicative capacity 8 to 12 people); "
        "3-burner gas barbecue (`BP-102`, `BBQ-G300`, indicative capacity 8 to 10 people). "
        "A charcoal barbecue needs compatible fuel and can use firelighters made for charcoal. "
        "The gas model requires suitable gas, **not sold in this catalog**. "
        "Capacities are teaching indications, not safety certifications.\n"
    )


@mcp.resource("bricopro://guides/compatibilite", name="compatibility_guide",
              title="BricoPro — accessory and fuel compatibility", mime_type="text/markdown")
def compatibility_guide() -> str:
    return (
        "# BricoPro — accessory and fuel compatibility\n\n"
        "**Documented compatibility:** charcoal 5 kg (`BP-103`), briquettes (`BP-104`), firelighters (`BP-105`) "
        "and the universal grill (`BP-107`) are compatible with `BBQ-C100` and `BBQ-F200`, **not** with "
        "`BBQ-G300` in this scenario. The tongs (`BP-106`) and the utensil kit (`BP-108`) are compatible with all "
        "three models. The `modeles_compatibles` fields of the data are authoritative for the checking tool. "
        "No gas reference exists, so gas must never be proposed as a BricoPro purchase.\n"
    )


@mcp.prompt(title="Choose a barbecue setup at BricoPro")
def choose_barbecue_setup(guests: int, budget_eur: float, fuel_preference: str | None = None) -> str:
    """Pick barbecue equipment at BricoPro for a group and budget."""
    return (
        f"At BricoPro, choose barbecue equipment suitable for {guests} guests, within {budget_eur:g} EUR, "
        f"with fuel preference: {fuel_preference or 'no preference'}. Check specifications, stock and the "
        "compatibility of every needed accessory with the tools. Separate the barbecue price from consumables. "
        "Flag what is not sold, notably gas for the gas model. Do not propose any food."
    )


if __name__ == "__main__":
    mcp.run("streamable-http", host="0.0.0.0", port=int(os.environ.get("PORT", "9003")),
            stateless_http=True, json_response=True)
