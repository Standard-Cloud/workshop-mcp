from conftest import api_client


def test_three_catalogs_total_35_entries():
    pm = api_client("prix-malin").get("/magasin/arrivages").json()["arrivages"]
    hm = api_client("hypermax").get("/api/v1/catalog/products").json()["items"]
    bp = api_client("bricopro").get("/pro/references").json()["references"]
    assert (len(pm), len(hm), len(bp)) == (9, 17, 9)
