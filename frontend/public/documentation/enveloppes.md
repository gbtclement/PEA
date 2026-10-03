# Enveloppes

Code :
- `backend/app/services/envelopes/rules.py` : registre des enveloppes et règles automatiques (fonctions pures) ;
- `backend/app/repositories/envelopes.py` : stockage, corrections manuelles et filtre SQL.

Une **enveloppe** est le compte sur lequel l'utilisateur investit : PEA, PEA-PME ou compte-titres. Chaque titre a un statut par enveloppe : `eligible`, `a_verifier` ou `non_eligible`.

## Les règles

| Code | Libellé | Règle |
|---|---|---|
| `pea` | PEA | Action dont le siège est dans l'UE ou l'EEE (deux premières lettres de l'ISIN) et soumise à l'IS. Foncières cotées (industrie « REIT… ») : `a_verifier`. ISIN absent ou invalide : `a_verifier`. ETF : `eligible` s'il est confirmé dans `seeds/etfs.csv` (source `seed`) ou si son nom contient le mot « PEA » (source `auto`), sinon `a_verifier` ; jamais déduit du pays de l'émetteur (un ETF irlandais ou luxembourgeois n'est pas éligible par défaut). Actions américaines (sans ISIN dans la source) : pays `US`, donc `non_eligible`. Indices : `non_eligible` (source `seed`). |
| `pea_pme` | PEA-PME | Éligible PEA, **et** moins de 5 000 salariés, **et** chiffre d'affaires ≤ 1,5 Md€, **et** capitalisation < 1 Md€. Une donnée manquante donne `a_verifier`. Un PEA non éligible ou « à vérifier » donne le même statut. ETF et indices : `non_eligible` (sauf correction). |
| `cto` | Compte-titres | Tous les titres. Rien n'est stocké. |

```python
country_from_isin("FR0000121014")  # → "FR"
```

## Le stockage

Table `security_envelopes` : une ligne par titre et par enveloppe à règle (`pea`, `pea_pme`).

| Colonne | Rôle |
|---|---|
| `status` | Statut final : `eligible`, `a_verifier` ou `non_eligible` |
| `source` | `auto` (règle), `seed` (liste de départ) ou `manual` (correction) |
| `override` | Correction manuelle, ou vide |

`Security.envelopes` est chargée avec le titre. `Security.eligible_envelopes` donne les codes où le titre est éligible ; c'est le champ `envelopes` des réponses de l'API (`["pea", "pea_pme"]`).

## Le recalcul

Les enveloppes sont recalculées :
- à chaque passage de la tâche `universe` (liste des titres) ;
- à chaque passage des fondamentaux (7 h 30 en semaine).

L'effectif (`fullTimeEmployees`) et le chiffre d'affaires (`totalRevenue`, en devise `financialCurrency`) viennent de Yahoo. Une réponse qui ne les donne pas **n'efface pas** les valeurs connues. Le chiffre d'affaires et la capitalisation sont convertis en euros avant la comparaison aux seuils. Une devise sans cours de change connu donne un montant inconnu, donc `a_verifier` (jamais compté 1 pour 1 comme des euros).

## Les corrections manuelles

Une correction prime toujours, et n'est jamais écrasée par les mises à jour. Elle est commune à tous les comptes, donc réservée à l'**administrateur** :
- carte « Enveloppes — corrections manuelles » de l'onglet Admin : choisir l'enveloppe, chercher le titre, choisir le statut ;
- ou `PATCH /api/securities/{id}/envelopes/{pea|pea_pme}` avec `{"override": "eligible" | "a_verifier" | "non_eligible" | null}` (`null` revient au calcul automatique).

Corriger le PEA d'un titre recalcule aussi son PEA-PME : passer une action en « non éligible PEA » la sort aussitôt du PEA-PME et du top 10 des membres qui ont choisi le PEA.

## Les enveloppes de l'utilisateur

- Colonne `user_settings.envelopes` (liste de codes), routes `GET` et `PUT /api/settings/envelopes`, carte « Mes enveloppes » des Réglages.
- Rien de coché, ou le compte-titres coché : **tous les titres**. Sinon, un titre doit être `eligible` dans au moins une des enveloppes choisies ; un titre « à vérifier » n'entre jamais dans le filtre.
- Le filtre s'applique à la lecture : top 10, plus fortes hausses et baisses, carte du marché, case « Mes enveloppes uniquement » des prévisions, prompt de l'assistant. Un visiteur sans compte voit tout.
- Les mails suivent le top 10 du membre : le récap du samedi et l'alerte « entrée dans le top 10 » comparent les photos du soir (`score_snapshots.top_pool`) filtrées par ses enveloppes.
- L'Explorer montre tous les titres ; son filtre « Enveloppe » restreint à la demande.

## Limites

!> Les enveloppes sont une **déduction**, à présenter comme telle dans l'interface. Le PEA-PME est une **estimation** : le critère du total de bilan (≤ 2 Md€) n'est pas connu.

- Le préfixe ISIN indique le pays d'émission, en général celui du siège, mais pas toujours.
- Une société peut perdre son éligibilité pour d'autres raisons (régime fiscal, statut particulier).
- `seeds/etfs.csv` liste à la main les ETF dont l'éligibilité au PEA est confirmée. Pour les milliers d'autres ETF, seul le mot « PEA » dans le nom vaut confirmation : les autres restent « à vérifier » tant qu'un admin ne les a pas corrigés.

## Migration d'octobre 2026

La migration `c5e7a9b1d3f5` a transformé les anciennes colonnes `securities.eligibility*` en lignes `pea` (la source `override` devient `manual`). Les lignes `pea_pme` apparaissent au premier passage des fondamentaux.
