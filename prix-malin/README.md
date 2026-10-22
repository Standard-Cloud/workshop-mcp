# Prix Malin — API des arrivages discount

## Contexte métier

Prix Malin est un **magasin alimentaire low cost** ouvert **tous les jours de 09:00 à 17:00**. Il propose un assortiment réduit : viande classique, frites, pain, sauces et boissons. Les prix sont généralement inférieurs à ceux de l'hypermarché, mais les disponibilités varient selon les arrivages. Un produit référencé peut être en rupture (`lots_disponibles = 0`).

**Règles du scénario** : aucune chips ; aucune viande bio ; aucun barbecue ni accessoire de bricolage. La viande et les frites sont moins chères qu'à HyperMax. Exception voulue : le cola est légèrement plus cher qu'à HyperMax.

## Contrat REST propre au marchand

Base d'URL fictive : `https://prix-malin.example/magasin`.

| Méthode et route | Réponse | Utilité |
|---|---|---|
| `GET /magasin/infos` | objet `enseigne` | Nom, positionnement, horaires |
| `GET /magasin/arrivages?famille=viande&disponible=true` | `{ "arrivages": [...] }` | Liste d'arrivages filtrable (filtres facultatifs) |
| `GET /magasin/arrivages/{code_arrivage}` | un objet arrivage | Fiche d'un lot ; 404 si identifiant inconnu |

La route de liste renvoie **tous les arrivages, y compris ceux en rupture**, si `disponible` n'est pas fourni. Le filtre `disponible=true` ne conserve que les lots dont le stock est strictement positif. Le filtre `famille` est une égalité exacte sur la famille enregistrée dans les données.

### Exemple de réponse `GET /magasin/arrivages/PM-001`

```json
{
  "code_arrivage": "PM-001",
  "libelle": "Saucisses de porc x6",
  "famille": "viande",
  "conditionnement": {"quantite": 6, "unite": "pièce"},
  "prix_centimes_ttc": 450,
  "lots_disponibles": 12,
  "etat": "en_stock"
}
```

## Données et règles d'implémentation

Le fichier adjacent [`donnees.json`](./donnees.json) contient l'objet `enseigne` et **9 arrivages**. Il constitue l'unique source de données. Le prix est un **entier en centimes TTC** (450 = 4,50 €), et le stock compte des **lots**, pas des articles individuels. `etat` est cohérent avec `lots_disponibles`. Les horaires sont une chaîne propre à ce fournisseur.

Backend **stateless**, lecture seule. Pas de panier, commande, paiement, réservation, modification de stock ou simulation d'écoulement des arrivages. Tous les horaires sont interprétés en fuseau `Europe/Paris` ; pour le workshop, les jours fériés sont ignorés.

## À gommer au niveau du futur MCP

Adapter les centimes en euros, `arrivages` en produits, `lots_disponibles` en quantité de lots en stock et la chaîne d'horaires en un format commun. Ne pas inventer les produits absents du catalogue.


---

# Spécification du serveur MCP — Prix Malin

## Rôle et périmètre

Le serveur **MCP Prix Malin** expose à un agent des capacités métier adaptées aux arrivages d'un discounter. Il appelle **uniquement l'API REST Prix Malin** ; il n'interroge ni HyperMax ni BricoPro. Son rôle est de convertir des prix en centimes, des lots disponibles et un horaire textuel en informations exploitables par l'agent. Les données restent en lecture seule : un contrôle de faisabilité n'est **ni une commande ni une réservation**.

- **Transport** : Streamable HTTP sur HTTPS, à l'URL indicative `https://prix-malin.example/mcp` (à remplacer au déploiement).
- **Primitives** : **3 Tools, 1 Resource, 2 Prompts**.
- **Données de référence** : `./donnees.json`, servies par les trois routes REST documentées ci-dessus.

## Tools (3)

| Outil MCP | Paramètres d'entrée | Réponse métier | Route(s) REST utilisées |
|---|---|---|---|
| `list_current_arrivals` | `family?: string`, `available_only?: boolean` | Arrivages, prix TTC en EUR, taille du lot, nombre de lots en stock, état | `GET /magasin/arrivages`, filtres `famille` et `disponible` |
| `get_arrival_details` | `arrival_code: string` | Fiche normalisée de l'arrivage demandé ; erreur explicite si inconnu | `GET /magasin/arrivages/{code_arrivage}` |
| `check_purchase_feasibility` | `items: [{arrival_code: string, packs: integer}]`, `shopping_time: string` (`HH:mm`, heure locale) | Faisabilité à l'heure demandée, disponibilité par ligne, coût TTC total des lots disponibles et alertes | `GET /magasin/infos` et `GET /magasin/arrivages` |

**Règles de `check_purchase_feasibility`** : `packs` désigne le nombre de lots ou conditionnements, pas le nombre de saucisses. Refuser les quantités négatives ou nulles, signaler les codes inexistants, les ruptures et les demandes supérieures au stock. Pour chaque ligne, renvoyer `requested_packs`, `available_packs`, `fulfillable_packs`, `line_total_eur` et `status` (`ok`, `partial`, `out_of_stock`, `not_found`). `fulfillable_packs = min(requested_packs, stock)` pour une référence valide. Si l'heure est hors de `[09:00, 17:00[`, le résultat global vaut `store_closed` et **aucune quantité n'est considérée achetable**. Pas de déduction du stock après simulation. Une même entrée produit ne doit apparaître qu'une fois ou doit être regroupée avant le calcul.

**Format de sortie** : objets JSON structurés. Utiliser des prix EUR à deux décimales, une devise `EUR`, un champ `merchant` à `Prix Malin` et des identifiants d'arrivage d'origine pour la traçabilité.

## Resource (1)

### `prixmalin://store/policy` — Politique des arrivages et horaires

Resource de type `text/markdown`, consultable volontairement par l'utilisateur ou l'agent selon les capacités du client MCP. Contenu proposé :

> Prix Malin est ouvert tous les jours de **09:00 à 17:00** (Europe/Paris). L'assortiment est limité et dépend des arrivages. Certains produits référencés sont en rupture. **Aucune viande bio, aucune chips et aucun équipement de barbecue** ne sont proposés. Les quantités affichées correspondent à des lots entiers. Aucun stock n'est réservé ; toute estimation de disponibilité est indicative. Les jours fériés sont ignorés pour cet exercice.

Cette ressource illustre une **règle métier**, distincte des données de catalogue fournies par les outils.

## Prompts (2)

Les prompts MCP sont des **modèles explicitement sélectionnables par l'utilisateur**, pas des instructions exécutées automatiquement à la connexion.

### `find_lowest_cost_meal`

- **Arguments** : `guests: integer`, `budget_eur: number`, `shopping_time: string` (`HH:mm`).
- **Message du prompt** : « Prépare les achats alimentaires les moins chers possibles chez Prix Malin pour {guests} personnes, avec un plafond de {budget_eur} EUR et un passage à {shopping_time}. Consulte les arrivages et leurs disponibilités, tiens compte des conditionnements entiers et vérifie la faisabilité. Affiche quantités, prix, coût total et besoins non couverts. Ne prétends pas que le marchand propose des articles absents. »
- **Démonstration** : recherche de lots économiques et calcul du budget.

### `adapt_to_arrivals`

- **Arguments** : `requested_items: string` (liste libre de besoins), `shopping_time: string` (`HH:mm`).
- **Message du prompt** : « Voici mes besoins : {requested_items}. Pour un passage chez Prix Malin à {shopping_time}, utilise les outils du marchand pour identifier les articles en stock, les ruptures et les absences du catalogue. Propose des substitutions seulement parmi les produits réellement proposés et distingue clairement substitution, rupture et indisponibilité structurelle. Indique les besoins à satisfaire auprès d'un autre marchand, sans supposer que tu y as accès. »
- **Démonstration** : adaptation aux ruptures, notamment aux brochettes de poulet indisponibles, et gestion de l'absence de chips.

## Démonstration du MCP

1. L'animateur fait découvrir les 3 Tools et appelle `list_current_arrivals`.
2. Le participant demande des brochettes, des frites et des chips ; l'outil détecte la rupture et le catalogue incomplet.
3. Le participant sélectionne **le premier puis le deuxième prompt** pour constater qu'un serveur MCP peut publier plusieurs modèles de travail.
4. L'agent consulte `prixmalin://store/policy` pour expliquer la fermeture à 17h et les limites des arrivages.

**Garde-fous** : aucune promesse de disponibilité future, pas d'achat, pas d'accès aux produits des autres magasins depuis ce MCP. Le choix global entre marchands relève de l'agent.
