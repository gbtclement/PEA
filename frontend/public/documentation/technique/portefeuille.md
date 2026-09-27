# Portefeuille et frais

## Frais de courtage

Code : `backend/app/services/fees.py`.

La grille par défaut est celle d'**Invest Store Intégral** (caisse de Paris) :

| Montant de l'ordre | Taux |
|---|---|
| jusqu'à 500 € | 0,48 % |
| jusqu'à 1 000 € | 0,18 % |
| au-delà | 0,12 % |

```python
broker_fee(400)   # → (1.92, 0.0048)
broker_fee(600)   # → (1.08, 0.0018)  le taux de la tranche s'applique au montant TOTAL
```

La grille de l'utilisateur est stockée en JSON dans `user_settings.fee_grid` et modifiable dans les Réglages. Elle sert pour :
- les frais proposés à la saisie d'un ordre ;
- `GET /api/fees/estimate` ;
- le simulateur ;
- les frais aller-retour des prévisions.

Les conversions de devises vers l'euro sont dans `services/fx.py`.

## Positions et PRU

Code : `backend/app/services/portfolio.py` (fonctions pures).

Les ordres sont rejoués dans l'ordre chronologique. Le même jour, les achats passent avant les ventes.

- **Achat :** `quantité += q` ; `coût += q × prix + frais`.
- **Vente :**
  - si `q` > quantité détenue → `OversellError`, que l'API transforme en refus lisible ;
  - `coût vendu = coût × q / quantité` ;
  - `plus-value réalisée += q × prix − frais − coût vendu` ;
  - le coût restant diminue d'autant, donc **le PRU des titres restants ne change pas**.
- **PRU** = `coût / quantité` (frais d'achat inclus).
- **Plus-value latente** = `quantité × cours − coût`.

La vérification de survente est faite **à la date de l'ordre**, y compris quand on modifie ou supprime un ordre passé : impossible de supprimer un achat dont les titres ont déjà été vendus.

## Compteur d'ordres

- Compte les ordres (achats et ventes) de l'**année civile**.
- Objectif `ordres_min` (12 par défaut) et frais de non-respect (96 €), réglables.
- **Rythme attendu** = `ordres_min × jours écoulés / jours de l'année`. Une alerte s'affiche si le nombre d'ordres est en dessous.
- API : `GET /api/orders/counter`.

## Évolution de la valeur

`GET /api/portfolio/history` reconstitue la valeur jour par jour depuis le premier ordre, à partir des ordres et des clôtures de `daily_prices`.

## Rafraîchissement

Les titres détenus sont automatiquement placés dans le palier **T1** : leur cours est rafraîchi toutes les 2 minutes en séance.
