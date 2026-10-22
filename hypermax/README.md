# HyperMax — API catalogue omnicanal

## Contexte métier

HyperMax est un **hypermarché généraliste** ouvert **tous les jours de 08:00 à 21:00**. Il propose une gamme large : viande, pain, boissons, chips, accompagnements, barbecues et consommables. C'est **le seul marchand à vendre de la viande bio**. Ses prix sont souvent plus élevés que ceux de Prix Malin, mais pas toujours (le cola coûte ici 1,15 € contre 1,30 € chez Prix Malin).

HyperMax permet d'acheter au même endroit presque tout le nécessaire d'un barbecue. Le barbecue compact référencé `BBQ-C100` est le même modèle que celui vendu par BricoPro, mais plus cher ici.

## Contrat REST propre au marchand

Base d'URL fictive : `https://hypermax.example/api/v1`.

| Méthode et route | Réponse | Utilité |
|---|---|---|
| `GET /api/v1/stores/HMX-001` | objet `store` | Identité et horaires du point de vente |
| `GET /api/v1/catalog/products?department=boucherie&organic=true` | `{ "items": [...], "total": N }` | Catalogue filtrable ; filtres facultatifs |
| `GET /api/v1/catalog/products/{sku}` | un objet produit | Détail produit ; 404 si SKU inconnu |

`department` filtre sur le champ `department`. `organic=true` conserve uniquement `isOrganic = true`, `organic=false` seulement `false`. Sans filtre, renvoyer tout le catalogue. `total` correspond au nombre d'articles renvoyés.

### Exemple de réponse `GET /api/v1/catalog/products/HMX-005`

```json
{
  "sku": "HMX-005",
  "title": "Saucisses de porc bio x6",
  "department": "boucherie",
  "pack": {"count": 6, "unit": "pièce"},
  "priceTtc": 9.9,
  "inventoryUnits": 10,
  "isOrganic": true
}
```

## Données et règles d'implémentation

Le fichier adjacent [`donnees.json`](./donnees.json) contient l'objet `store` et **17 produits**. Le prix est un **nombre en euros TTC**, contrairement aux centimes de Prix Malin. `inventoryUnits` désigne le **nombre de conditionnements disponibles** et non les unités composant un pack. `isOrganic` est renseigné sur chaque produit, avec la valeur `true` uniquement pour les deux références de viande bio.

Les horaires sont représentés par l'objet `businessHours`. Pour le workshop, l'établissement est ouvert tous les jours selon la même plage horaire, jours fériés ignorés.

Backend **stateless**, lecture seule. Aucun panier, commande, paiement, réservation, calcul de livraison ni changement de stock.

## À gommer au niveau du futur MCP

Adapter `catalog`, `sku`, `department`, `priceTtc`, `inventoryUnits` et `isOrganic` vers des concepts produits communs. Conserver la qualité bio pour les arbitrages métier, ainsi que `manufacturerModel` pour reconnaître une référence identique dans un autre magasin.


---

# Spécification du serveur MCP — HyperMax

## Rôle et périmètre

Le serveur **MCP HyperMax** traduit le catalogue généraliste de l'hypermarché en outils adaptés à la recherche de produits, à la sélection bio et à la prise en compte des horaires. Il ne consomme **que l'API REST HyperMax** et ne connaît pas les stocks concurrents.

- **Transport** : Streamable HTTP sur HTTPS, URL indicative `https://hypermax.example/mcp`.
- **Primitives** : **3 Tools, 1 Resource, 1 Prompt**.
- **Données de référence** : `./donnees.json` derrière les routes REST propres à HyperMax.

## Tools (3)

| Outil MCP | Paramètres d'entrée | Réponse métier | Route(s) REST utilisées |
|---|---|---|---|
| `search_catalog` | `query?: string`, `department?: string`, `organic_only?: boolean`, `max_price_eur?: number`, `in_stock_only?: boolean` | Catalogue filtré, prix TTC EUR, stock, conditionnement, label bio et modèle fabricant éventuel | `GET /api/v1/catalog/products` |
| `get_product_information` | `sku: string` | Fiche détaillée normalisée d'un produit | `GET /api/v1/catalog/products/{sku}` |
| `get_store_opening_status` | `shopping_time: string` (`HH:mm`, heure locale) | `is_open`, `opens_at`, `closes_at`, `next_opening` et fuseau | `GET /api/v1/stores/HMX-001` |

**Règles d'adaptation** : l'API REST filtre déjà par `department` et `organic`. Les critères `query`, `max_price_eur` et `in_stock_only` sont appliqués **en lecture seule par le MCP**, après récupération du catalogue. `query` est une correspondance textuelle insensible à la casse sur `title`, et **non une recherche vectorielle**. `organic_only=true` correspond strictement à `isOrganic=true`. Si aucun filtre n'est fourni, la recherche retourne tous les produits. Le magasin ouvre à 08:00 et ferme à 21:00 : `[08:00, 21:00[`. `next_opening` est calculé pour le jour suivant si l'heure demandée est après la fermeture ; avant 08:00, il vaut 08:00 le jour même. Les jours fériés sont ignorés.

**Format de sortie** : JSON structuré incluant `merchant: "HyperMax"`, identifiant `sku`, `price_eur`, `stock_packs`, `organic` et, si disponible, `manufacturer_model`. Aucune comparaison de prix concurrent n'est effectuée ici.

## Resource (1)

### `hypermax://catalog/categories` — Départements et périmètre bio

Resource `text/markdown` :

> Départements du catalogue : `boucherie`, `épicerie`, `surgelés`, `boulangerie`, `boissons`, `traiteur`, `plein_air`. Le filtre bio porte sur `isOrganic`, et non sur le seul nom commercial d'un article. Dans ce scénario, **seules deux références de viande sont bio** (`HMX-005`, `HMX-006`). HyperMax est ouvert de **08:00 à 21:00** tous les jours (Europe/Paris). Le magasin commercialise aliments et matériels de barbecue.

Cette ressource illustre un **référentiel métier** relativement stable, sans multiplier les routes REST.

## Prompt (1)

### `prepare_organic_barbecue`

- **Arguments** : `guests: integer`, `budget_eur: number`, `shopping_time: string` (`HH:mm`).
- **Message du prompt** : « Organise un barbecue pour {guests} personnes avec de la viande exclusivement bio et un budget maximum de {budget_eur} EUR. Recherche uniquement les viandes marquées bio dans le catalogue HyperMax ; complète si utile avec les accompagnements, boissons ou équipements du même marchand. Vérifie les stocks et l'ouverture à {shopping_time}. Présente les lots, le prix total et les contraintes ou éléments manquants. Ne qualifie jamais de bio une viande dont l'attribut `organic` vaut false. »
- **Démonstration** : filtrage sur un critère métier explicite.

## Démonstration du MCP

1. Recherche `organic_only=true` pour montrer que seul HyperMax propose des références bio.
2. Recherche du cola 1,5 L : le prix doit être vérifié, et non supposé plus cher que chez Prix Malin.
3. Lecture de `hypermax://catalog/categories` puis utilisation du prompt de barbecue bio.
4. Comparaison inter-marchands laissée **à l'agent**, jamais calculée par le serveur HyperMax.

**Garde-fous** : réponses strictement issues du catalogue et des horaires ; lecture seule, pas de réservation et pas de traitement d'achat.
