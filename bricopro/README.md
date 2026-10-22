# BricoPro — API références et stock de l'agence

## Contexte métier

BricoPro est un **magasin de bricolage et d'équipement extérieur**, ouvert **tous les jours de 07:00 à 19:00**. Il vend barbecues, charbon, briquettes, allume-feu, pinces et accessoires. **Aucun produit alimentaire** : ni viande, ni chips, ni boissons.

BricoPro est compétitif sur ses spécialités. Le barbecue compact de modèle fabricant `BBQ-C100` coûte 39,90 € chez BricoPro contre 49,90 € chez HyperMax. Le charbon 5 kg, l'allume-feu et la pince sont également moins chers à BricoPro.

## Contrat REST propre au marchand

Base d'URL fictive : `https://bricopro.example/pro`.

| Méthode et route | Réponse | Utilité |
|---|---|---|
| `GET /pro/agence` | objet `agence` | Horaires et identité de l'agence |
| `GET /pro/references?rayon=barbecues&en_stock=true` | `{ "references": [...] }` | Liste filtrable par rayon et disponibilité |
| `GET /pro/references/{reference}` | un objet référence | Fiche technique et stock ; 404 si identifiant inconnu |

Le paramètre `rayon` correspond exactement au champ `rayon`. `en_stock=true` conserve les références dont `disponibilite.en_stock` est vraie. Sans filtre, renvoyer toutes les références.

### Exemple de réponse `GET /pro/references/BP-100`

```json
{
  "reference": "BP-100",
  "designation": "Barbecue charbon compact",
  "rayon": "barbecues",
  "tarif": {"montant_ttc_centimes": 3990, "devise": "EUR"},
  "disponibilite": {"en_stock": true, "quantite_cond": 8},
  "contenu": {"valeur": 1, "mesure": "pièce"},
  "modele_fabricant": "BBQ-C100"
}
```

## Données et règles d'implémentation

Le fichier adjacent [`donnees.json`](./donnees.json) contient l'objet `agence` et **9 références**. Le prix est placé dans `tarif.montant_ttc_centimes` (en **centimes TTC**) ; le stock est imbriqué dans `disponibilite.quantite_cond` (nombre de conditionnements). Les catégories sont appelées `rayon`, et les horaires ont une structure propre à l'agence.

Tous les articles sont du matériel ou des consommables non alimentaires. Pour le workshop, horaires identiques chaque jour, jours fériés ignorés.

Backend **stateless**, lecture seule : pas de réservation, panier, achat, paiement, vente, modification de stock ni consultation de livraison.

## À gommer au niveau du futur MCP

Adapter `reference`, `designation`, `rayon`, `tarif`, `disponibilite` et `contenu` en une structure de produit uniforme. Préserver `modele_fabricant` pour permettre la comparaison du barbecue compact avec celui d'HyperMax.


---

# Spécification du serveur MCP — BricoPro

## Rôle et périmètre

Le serveur **MCP BricoPro** expose une expertise métier sur les équipements et les combustibles. Il traduit une API orientée références, tarifs imbriqués et fiches techniques en outils compréhensibles par l'agent. **Aucun aliment** n'est vendu par ce marchand.

- **Transport** : Streamable HTTP sur HTTPS, URL indicative `https://bricopro.example/mcp`.
- **Primitives** : **3 Tools, 2 Resources, 1 Prompt**.
- **Données de référence** : `./donnees.json` via les trois routes REST BricoPro existantes.

## Tools (3)

| Outil MCP | Paramètres d'entrée | Réponse métier | Route(s) REST utilisées |
|---|---|---|---|
| `find_barbecue_equipment` | `category?: string`, `fuel_type?: string`, `max_price_eur?: number`, `in_stock_only?: boolean` | Équipements et accessoires, prix TTC EUR, stocks et caractéristiques disponibles | `GET /pro/references` |
| `get_equipment_specs` | `reference: string` | Fiche d'équipement avec modèle fabricant, type de combustible, capacité et compatibilités si renseignés | `GET /pro/references/{reference}` |
| `check_accessory_compatibility` | `barbecue_reference: string`, `accessory_reference: string` | `compatible: boolean | null`, `reason` et références contrôlées | `GET /pro/references/{reference}` (pour les deux références) |

**Règles d'adaptation** : `category` correspond au `rayon` de l'API. `fuel_type` ne s'applique qu'aux produits portant `type_combustible` ou `combustible_requis` ; ce n'est pas un filtre de recherche dans une base externe. `max_price_eur` est converti en centimes. Les stocks proviennent de `disponibilite.quantite_cond`. Dans `check_accessory_compatibility`, lire `modele_fabricant` du barbecue puis comparer avec la liste explicite `modeles_compatibles` de l'accessoire. `compatible=false` signifie **incompatibilité documentée** ; `compatible=null` signifie **information absente, vérification impossible**. Un produit non identifié génère une erreur métier claire. Ne pas déduire la compatibilité d'un simple intitulé « universel ».

**Format de sortie** : JSON structuré, `merchant: "BricoPro"`, `price_eur`, `stock_packs`, références d'origine, attributs techniques lorsqu'ils sont présents. Le MCP ne fabrique pas de disponibilité ni de référence manquante.

## Resources (2)

Ces deux URI démontrent qu'un serveur MCP peut publier **plusieurs ressources**, avec des sujets et des contenus différents.

### `bricopro://guides/barbecue` — Choix d'un barbecue

Resource `text/markdown` :

> **Modèles proposés** : barbecue compact à charbon (`BP-100`, `BBQ-C100`, capacité indicative 4 à 6 personnes) ; barbecue familial à charbon (`BP-101`, `BBQ-F200`, capacité indicative 8 à 12 personnes) ; barbecue gaz 3 brûleurs (`BP-102`, `BBQ-G300`, capacité indicative 8 à 10 personnes). Un barbecue à charbon nécessite un combustible compatible et peut utiliser un allume-feu prévu pour le charbon. Le modèle à gaz requiert un combustible gaz adapté, **non vendu dans ce catalogue**. Les capacités sont des indications pédagogiques et non des certifications de sécurité.

### `bricopro://guides/compatibilite` — Compatibilités de l'assortiment

Resource `text/markdown` :

> **Compatibilités documentées** : le charbon 5 kg (`BP-103`), les briquettes (`BP-104`), les allume-feu (`BP-105`) et la grille universelle (`BP-107`) sont compatibles avec `BBQ-C100` et `BBQ-F200`, **pas** avec `BBQ-G300` dans ce scénario. La pince (`BP-106`) et le kit d'ustensiles (`BP-108`) sont compatibles avec les trois modèles. Les champs `modeles_compatibles` de `donnees.json` font foi pour l'outil de vérification. L'absence d'une référence de gaz interdit de proposer son achat chez BricoPro.

**Rôle pédagogique** : une ressource informe sur le **choix**, l'autre sur la **compatibilité**. Les outils vérifient ensuite une référence précise et son stock. Les textes des ressources doivent rester cohérents avec les données JSON.

## Prompt (1)

### `choose_barbecue_setup`

- **Arguments** : `guests: integer`, `budget_eur: number`, `fuel_preference?: string` (`charbon`, `gaz` ou non renseigné).
- **Message du prompt** : « Choisis chez BricoPro un équipement de barbecue adapté à {guests} personnes, dans la limite de {budget_eur} EUR, avec la préférence de combustible {fuel_preference}. Consulte les caractéristiques, vérifie les stocks et la compatibilité des accessoires nécessaires. Distingue le prix du barbecue de celui des consommables. Signale ce qui n'est pas vendu, notamment le gaz pour le modèle à gaz. Ne propose aucun aliment. »
- **Démonstration** : choix argumenté et vérification technique outillée.

## Démonstration du MCP

1. L'agent lit **les deux ressources** BricoPro et distingue conseils généraux et tableau de compatibilités.
2. L'utilisateur demande un barbecue pour 10 personnes avec du charbon ; l'agent explore le modèle familial.
3. L'agent vérifie les combustibles et accessoires par `check_accessory_compatibility` au lieu de supposer qu'ils conviennent.
4. Il compare ensuite le barbecue compact `BBQ-C100` avec celui d'HyperMax **au niveau de l'agent**, pas dans BricoPro.

**Garde-fous** : lecture seule, aucune promesse de sécurité technique ou de disponibilité future ; pas de commande ni d'autres fournisseurs intégrés à ce MCP.
