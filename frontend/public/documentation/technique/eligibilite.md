# Éligibilité PEA

Code : `backend/app/services/eligibility/rules.py`.

## La règle

Un titre est éligible au PEA si la société a son **siège dans l'Union européenne ou l'Espace économique européen** et est soumise à l'impôt sur les sociétés.

Le pays du siège est déduit des **deux premières lettres du code ISIN** :

```python
country_from_isin("FR0000121014")  # → "FR"
```

| Cas | Statut |
|---|---|
| Pays dans l'UE-27 ou l'EEE (Islande, Liechtenstein, Norvège) | `eligible` |
| Secteur de type REIT/SIIC (foncières cotées, exonérées d'IS, donc en principe exclues) | `a_verifier` |
| ISIN absent ou invalide | `a_verifier` |
| Autre pays | `non_eligible` |

## La correction manuelle

`securities.eligibility_override` peut valoir `eligible` ou `non_eligible`. Elle se règle depuis les Réglages, ou avec `PATCH /api/securities/{id}/eligibility`.

`effective_eligibility()` renvoie le statut final et sa source :

- s'il y a une correction : le statut corrigé, source `override` ;
- sinon : le statut automatique.

La correction n'est **jamais écrasée** par la mise à jour quotidienne de l'univers.

## Limites

!> L'éligibilité est une **déduction**, à présenter comme telle dans l'interface.

- Le préfixe ISIN indique le pays d'émission, en général celui du siège, mais pas toujours.
- Une société peut perdre son éligibilité pour d'autres raisons (régime fiscal, statut particulier).
- Les ETF sont listés à la main dans `seeds/etfs.csv` : seuls des ETF éligibles y figurent.
