import json

import pytest

from conftest import ROOT, api_client

DATA = json.loads((ROOT / "prix-malin" / "donnees.json").read_text(encoding="utf-8"))
client = api_client("prix-malin")


def codes(response):
    return [a["code_arrivage"] for a in response.json()["arrivages"]]


def test_infos_returns_enseigne():
    r = client.get("/magasin/infos")
    assert r.status_code == 200
    assert r.json() == DATA["enseigne"]


def test_list_returns_all_nine_arrivals_including_sold_out():
    r = client.get("/magasin/arrivages")
    assert r.status_code == 200
    assert r.json() == {"arrivages": DATA["arrivages"]}
    assert len(codes(r)) == 9
    assert "PM-004" in codes(r)


@pytest.mark.parametrize(
    "query, expected",
    [
        ("famille=viande", ["PM-001", "PM-002", "PM-003", "PM-004"]),
        ("disponible=false", ["PM-004"]),
        ("famille=viande&disponible=true", ["PM-001", "PM-002", "PM-003"]),
        ("famille=boisson", ["PM-008", "PM-009"]),
        ("famille=chips", []),
        ("famille=Viande", []),
    ],
)
def test_list_filters(query, expected):
    r = client.get(f"/magasin/arrivages?{query}")
    assert r.status_code == 200
    assert codes(r) == expected


def test_disponible_true_keeps_only_positive_stock():
    r = client.get("/magasin/arrivages?disponible=true")
    assert len(codes(r)) == 8
    assert all(a["lots_disponibles"] > 0 for a in r.json()["arrivages"])


def test_invalid_boolean_is_rejected():
    assert client.get("/magasin/arrivages?disponible=peut-etre").status_code == 422


def test_get_arrival_returns_exact_fixture():
    r = client.get("/magasin/arrivages/PM-001")
    assert r.status_code == 200
    assert r.json() == DATA["arrivages"][0]
    assert r.json()["prix_centimes_ttc"] == 450


def test_sold_out_skewers_are_present():
    r = client.get("/magasin/arrivages/PM-004")
    assert r.json()["lots_disponibles"] == 0
    assert r.json()["etat"] == "rupture"


def test_unknown_arrival_returns_404():
    assert client.get("/magasin/arrivages/PM-999").status_code == 404


def test_repeated_reads_are_identical():
    assert client.get("/magasin/arrivages").json() == client.get("/magasin/arrivages").json()
