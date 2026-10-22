# Codex task — Implement the three merchant REST APIs using TDD

## Goal

Implement **three independent, read-only, stateless REST APIs** for a business-oriented MCP workshop. This task implements **only the REST backends**, **not** the MCP servers, agent, shopping cart, payment, authentication, or deployment. The three vendors deliberately expose **different routes, data schemas and query conventions**. Do **not** unify their public API contracts: a later MCP layer will adapt them.

## Authoritative files

- [`prix-malin/README.md`](prix-malin/README.md) and [`prix-malin/donnees.json`](prix-malin/donnees.json)
- [`hypermax/README.md`](hypermax/README.md) and [`hypermax/donnees.json`](hypermax/donnees.json)
- [`bricopro/README.md`](bricopro/README.md) and [`bricopro/donnees.json`](bricopro/donnees.json)

The REST specifications in the top sections of the merchant README files are authoritative. The later MCP sections are **future integration specifications**, not part of this implementation. JSON fixtures are immutable inputs; do not invent products, modify prices/stocks or convert field names in REST responses.

## Stack and structure

Prefer **Python 3.12+ / FastAPI / pytest / httpx** for minimal workshop setup, unless the repository already establishes a different stack. Keep the three apps logically and operationally independent: each can be started and tested independently with its own OpenAPI docs. Shared test helpers or bootstrapping are fine, but **no shared public merchant schema** and no centralized aggregator. Loading fixture files into memory at startup is acceptable. No database, no external services.

Suggest a straightforward directory structure (adapt to conventions if present):

```
prix-malin/README.md
prix-malin/donnees.json
prix-malin/app.py
hypermax/README.md
hypermax/donnees.json
hypermax/app.py
bricopro/README.md
bricopro/donnees.json
bricopro/app.py
tests/test_prix_malin.py
tests/test_hypermax.py
tests/test_bricopro.py
pyproject.toml
```

It should be possible to run three independent instances on different ports, e.g. 8001, 8002, 8003. Provide brief reproducible commands in the repository's main README and/or merchant READMEs. Keep all endpoints JSON-based and accessible via FastAPI `/docs`.

## Required TDD process — RED / GREEN / REFACTOR

1. Start by reading all six authoritative files and **write tests before writing implementations**.
2. Run the tests and record **meaningful initial failures** (RED). If commit access is available, create a tests-first commit.
3. Implement the **smallest code** satisfying the tests (GREEN); rerun the tests.
4. Refactor for clarity with **unchanged behavior**; rerun all tests.
5. In the final report, give evidence of RED and GREEN (commands and summarized outputs), test totals, changes and any deviations. Do **not** claim TDD without showing the initial failing run.
6. Do not weaken or delete tests to obtain GREEN.

Prefer parametrized endpoint tests. Assert exact merchant-specific response shapes, values and filtering semantics, and failures for invalid inputs. Keep tests deterministic and network-free.

## API 1 — Prix Malin

Required routes:

- `GET /magasin/infos`: return the `enseigne` object.
- `GET /magasin/arrivages`: `{ "arrivages": [...] }`, optional filters `famille` (exact match) and `disponible` (boolean). Without filters, include **all nine arrivals**, including those with zero stock. `disponible=true` selects `lots_disponibles > 0`; `disponible=false` selects zero-stock arrivals.
- `GET /magasin/arrivages/{code_arrivage}`: exact fixture arrival, HTTP 404 for an unknown code.

Validate: prices are `prix_centimes_ttc` integer cent values; stocks represent **packs**; the chicken skewers `PM-004` are present but sold out; chips, organic meat and BBQ equipment are not present. No changes to stock.

## API 2 — HyperMax

Required routes:

- `GET /api/v1/stores/HMX-001`: return the `store` object. Return 404 for any other store identifier if a parameterized store route is used.
- `GET /api/v1/catalog/products`: `{ "items": [...], "total": N }`, optional filters `department` (exact match) and `organic` (boolean), composable. The `total` equals the number of filtered products, not the original catalogue size. With no filters return **all 17 products**.
- `GET /api/v1/catalog/products/{sku}`: exact fixture product, HTTP 404 if unknown.

Validate: organic-only products are the two organic meat items; `priceTtc` is expressed in EUR; the cola price is **EUR 1.15**, less than Prix Malin's cola. Include nonfood products in the catalogue.

## API 3 — BricoPro

Required routes:

- `GET /pro/agence`: return the `agence` object.
- `GET /pro/references`: `{ "references": [...] }`, optional filters `rayon` (exact match) and `en_stock` (boolean). Without filters return **all nine references**. `en_stock=true` follows `disponibilite.en_stock` as specified in the fixture; a false filter should select `false` items, if any.
- `GET /pro/references/{reference}`: exact fixture reference, HTTP 404 if unknown.

Validate: `tarif.montant_ttc_centimes` is an integer number of cents; inventory is in `disponibilite`; retain technical fields `modele_fabricant`, `type_combustible`, `capacite_personnes`, `modeles_compatibles` when present. `BP-100` is the compact `BBQ-C100` model; **no food items**.

## Cross-cutting acceptance tests

- All **nine routes** work and return unmodified merchant-specific JSON shapes.
- Three catalogs return **9 + 17 + 9 = 35** fixture entries.
- Empty filter matches return empty collection with HTTP 200 (and `total: 0` for HyperMax).
- Combining filters is intersection, not union.
- Use appropriate 400/422 errors for malformed query booleans, with consistent behavior and tests.
- Unknown product references return HTTP 404, not an empty object or 500.
- Repeated GETs are identical: read-only, no stock decrement, no side effects.
- Store opening-hours payloads remain as supplied in each fixture. No simulated clock or mutable availability.
- Independent OpenAPI documentation per app; a short runbook shows how to start all three apps and try their URLs via a browser.
- Add a small CI job to run `pytest` on push/PR if this is a GitHub repository, without needing secrets.

## Scope boundaries

**Do not implement MCP yet** (`Tools`, `Resources`, `Prompts`, Streamable HTTP). Do not implement cart, checkout, order, authentication, inventory updates, background tasks, shipping or persistence. Do not add unnecessary abstractions. Do not rewrite the business specs or JSON fixtures unless a demonstrable contradiction prevents implementation; flag contradictions instead.

## Deliverables

- 3 independently startable FastAPI services with native paths and schemas.
- A test suite written first, with RED/GREEN evidence and passing results.
- Minimal dependency and run/test instructions, examples of `curl` and browser `/docs` URLs.
- Optional small GitHub Actions pytest workflow.
- One summary of coverage, decisions and known limitations.

**Definition of done:** all tests pass locally, all nine endpoints conform to the existing READMEs and JSON fixtures, and no MCP implementation has been introduced prematurely.
