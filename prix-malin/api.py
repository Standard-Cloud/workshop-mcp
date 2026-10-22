"""Prix Malin REST API — read-only discount food arrivals."""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException

DATA = json.loads((Path(__file__).parent / "donnees.json").read_text(encoding="utf-8"))

app = FastAPI(title="Prix Malin API", description="Arrivages du discounter alimentaire (lecture seule).")


@app.get("/magasin/infos")
def infos():
    return DATA["enseigne"]


@app.get("/magasin/arrivages")
def arrivages(famille: str | None = None, disponible: bool | None = None):
    items = DATA["arrivages"]
    if famille is not None:
        items = [a for a in items if a["famille"] == famille]
    if disponible is not None:
        items = [a for a in items if (a["lots_disponibles"] > 0) == disponible]
    return {"arrivages": items}


@app.get("/magasin/arrivages/{code_arrivage}")
def arrivage(code_arrivage: str):
    for a in DATA["arrivages"]:
        if a["code_arrivage"] == code_arrivage:
            return a
    raise HTTPException(404, f"Arrivage inconnu : {code_arrivage}")
