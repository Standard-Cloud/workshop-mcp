"""HyperMax REST API — read-only hypermarket catalog."""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException

DATA = json.loads((Path(__file__).parent / "donnees.json").read_text(encoding="utf-8"))

app = FastAPI(title="HyperMax API", description="Omnichannel catalog of the HyperMax hypermarket (read-only).")


@app.get("/api/v1/stores/{store_id}")
def store(store_id: str):
    if store_id != DATA["store"]["storeId"]:
        raise HTTPException(404, f"Unknown store: {store_id}")
    return DATA["store"]


@app.get("/api/v1/catalog/products")
def products(department: str | None = None, organic: bool | None = None):
    items = DATA["catalog"]
    if department is not None:
        items = [p for p in items if p["department"] == department]
    if organic is not None:
        items = [p for p in items if p["isOrganic"] == organic]
    return {"items": items, "total": len(items)}


@app.get("/api/v1/catalog/products/{sku}")
def product(sku: str):
    for p in DATA["catalog"]:
        if p["sku"] == sku:
            return p
    raise HTTPException(404, f"Unknown SKU: {sku}")
