import json

import pytest

from conftest import ROOT, api_client

DATA = json.loads((ROOT / "hypermax" / "donnees.json").read_text(encoding="utf-8"))
client = api_client("hypermax")


def skus(response):
    return [p["sku"] for p in response.json()["items"]]


def test_store_returns_store_object():
    r = client.get("/api/v1/stores/HMX-001")
    assert r.status_code == 200
    assert r.json() == DATA["store"]


def test_unknown_store_returns_404():
    assert client.get("/api/v1/stores/HMX-999").status_code == 404


def test_catalog_returns_all_seventeen_products():
    r = client.get("/api/v1/catalog/products")
    assert r.status_code == 200
    assert r.json() == {"items": DATA["catalog"], "total": 17}


@pytest.mark.parametrize(
    "query, expected",
    [
        ("organic=true", ["HMX-005", "HMX-006"]),
        ("department=boucherie&organic=true", ["HMX-005", "HMX-006"]),
        ("department=boissons", ["HMX-011", "HMX-012"]),
        ("department=boissons&organic=true", []),
        ("department=inconnu", []),
    ],
)
def test_catalog_filters(query, expected):
    r = client.get(f"/api/v1/catalog/products?{query}")
    assert r.status_code == 200
    assert skus(r) == expected
    assert r.json()["total"] == len(expected)


def test_organic_false_excludes_organic_items():
    r = client.get("/api/v1/catalog/products?organic=false")
    assert r.json()["total"] == 15
    assert "HMX-005" not in skus(r)


def test_nonfood_products_are_in_catalog():
    r = client.get("/api/v1/catalog/products?department=plein_air")
    assert skus(r) == ["HMX-014", "HMX-015", "HMX-016", "HMX-017"]


def test_invalid_boolean_is_rejected():
    assert client.get("/api/v1/catalog/products?organic=bof").status_code == 422


def test_get_product_returns_exact_fixture():
    r = client.get("/api/v1/catalog/products/HMX-011")
    assert r.status_code == 200
    assert r.json() == DATA["catalog"][10]
    assert r.json()["priceTtc"] == 1.15


def test_unknown_product_returns_404():
    assert client.get("/api/v1/catalog/products/HMX-999").status_code == 404
