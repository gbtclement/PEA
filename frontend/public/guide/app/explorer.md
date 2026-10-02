# Explorer et ETF

## Explorer

La liste de **toutes les actions** suivies par l'application, environ 1 800, dans un tableau qui reste fluide même avec des milliers de lignes.

### Rechercher

Tapez un nom (`LVMH`), un ticker (`MC`) ou un code ISIN (`FR0000121014`).

### Filtrer

Secteur, pays, place de cotation, score minimum, prix minimum et maximum, enveloppe (PEA, PEA-PME), favoris, et « liquides uniquement » (les actions assez échangées).

> **Exemple :** pour trouver des entreprises françaises solides et bien notées, choisissez le pays France, un score minimum de 65 et « liquides uniquement ». Triez ensuite par rendement du dividende.

### Colonnes

| Colonne | Signification |
|---|---|
| ⭐ | Ajouter ou retirer des favoris |
| Nom, ticker | L'entreprise et son code en bourse |
| Cours | Dernier prix connu |
| 1 j, 1 sem, 1 mois, 1 an | Variation du cours sur chaque période |
| Score | Note sur 100 (voir [Comprendre le score](app/score.md)) |
| PER | Prix payé pour 1 € de bénéfice annuel (voir [Juger une entreprise](bourse/analyse-fondamentale.md)) |
| Rendement | Dividende annuel en % du cours |
| Mini-courbe | L'allure du cours sur les derniers mois |

Cliquez sur un en-tête de colonne pour trier. Le tri par nom est « naturel » : `2CRSI` passe avant `ABC`.

### L'adresse garde vos choix

Les filtres et le tri sont enregistrés dans l'adresse de la page. Vous pouvez ajouter la page à vos favoris du navigateur avec vos réglages, ou revenir en arrière sans perdre votre recherche.

## ETF

Même écran, limité aux **ETF** suivis par l'application, avec leur badge PEA quand ils sont éligibles. Un ETF est un panier d'actions qui suit un indice entier : en achetant un ETF CAC 40, vous possédez un petit morceau des 40 entreprises. Voir [Les ETF](bourse/etf.md).

Les ETF n'ont pas de bilan ni de bénéfices : leur score est **uniquement technique**, c'est-à-dire basé sur l'évolution de leur cours, puis ramené sur 100.

## Badges d'enveloppe

| Badge | Signification |
|---|---|
| **PEA** | Siège de l'entreprise dans l'Union européenne ou l'Espace économique européen : le titre peut aller dans un PEA |
| **PEA-PME** | En plus, une entreprise de taille moyenne : moins de 5 000 salariés, chiffre d'affaires d'au plus 1,5 Md€ et capitalisation sous 1 Md€. C'est une **estimation** |
| Pas de badge | Non éligible, ou cas douteux à vérifier : par exemple une société américaine, ou une foncière cotée (en principe exclue du PEA) |

Le filtre **Enveloppe** de l'Explorer ne garde que les titres qui portent le badge choisi. Un compte-titres accepte tous les titres : il n'a pas de badge.

!> Il n'existe pas de liste officielle complète des titres éligibles au PEA ou au PEA-PME : l'application les **déduit** du pays du siège et de la taille de l'entreprise. Avant un achat important, vérifiez que votre banque accepte le titre dans votre enveloppe. Un badge faux se signale à l'administrateur du site, qui peut le corriger (voir [Réglages](app/reglages.md)).
