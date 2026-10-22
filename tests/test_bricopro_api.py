import json

import pytest

from conftest import ROOT, api_client

DATA = json.loads((ROOT / "bricopro" / "donnees.json").read_text(encoding="utf-8"))
client = api_client("bricopro")


def refs(response):
    return [r["reference"] for r in response.json()["references"]]


def test_agence_returns_agence_object():
    r = client.get("/pro/agence")
    assert r.status_code == 200
    assert r.json() == DATA["agence"]


def test_list_returns_all_nine_references():
    r = client.get("/pro/references")
    assert r.status_code == 200
    assert r.json() == {"references": DATA["references"]}


@pytest.mark.parametrize(
    "query, expected",
    [
        ("rayon=barbecues", ["BP-100", "BP-101", "BP-102"]),
        ("rayon=combustibles&en_stock=true", ["BP-103", "BP-104"]),
        ("en_stock=false", []),
        ("rayon=boucherie", []),
    ],
)
def test_list_filters(query, expected):
    r = client.get(f"/pro/references?{query}")
    assert r.status_code == 200
    assert refs(r) == expected


def test_invalid_boolean_is_rejected():
    assert client.get("/pro/references?en_stock=oui-non").status_code == 422


def test_get_reference_keeps_technical_fields():
    r = client.get("/pro/references/BP-100")
    assert r.status_code == 200
    body = r.json()
    assert body == DATA["references"][0]
    assert body["modele_fabricant"] == "BBQ-C100"
    assert body["tarif"]["montant_ttc_centimes"] == 3990
    assert body["capacite_personnes"] == {"min": 4, "max": 6}


def test_accessory_keeps_compatible_models():
    r = client.get("/pro/references/BP-103")
    assert r.json()["modeles_compatibles"] == ["BBQ-C100", "BBQ-F200"]


def test_unknown_reference_returns_404():
    assert client.get("/pro/references/BP-999").status_code == 404
