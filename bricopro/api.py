"""BricoPro REST API — read-only DIY and barbecue equipment references."""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException

DATA = json.loads((Path(__file__).parent / "donnees.json").read_text(encoding="utf-8"))

app = FastAPI(title="BricoPro API", description="Références et stock de l'agence BricoPro (lecture seule).")


@app.get("/pro/agence")
def agence():
    return DATA["agence"]


@app.get("/pro/references")
def references(rayon: str | None = None, en_stock: bool | None = None):
    items = DATA["references"]
    if rayon is not None:
        items = [r for r in items if r["rayon"] == rayon]
    if en_stock is not None:
        items = [r for r in items if r["disponibilite"]["en_stock"] == en_stock]
    return {"references": items}


@app.get("/pro/references/{reference}")
def reference(reference: str):
    for r in DATA["references"]:
        if r["reference"] == reference:
            return r
    raise HTTPException(404, f"Référence inconnue : {reference}")
