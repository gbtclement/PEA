# Réglages

## Assistant IA

- **Clé API Claude** : saisie une fois, puis affichée seulement comme « configurée ». Elle est chiffrée en base avec `APP_SECRET` et n'est jamais renvoyée au navigateur.
- **Modèle** utilisé par l'assistant.

## Frais et compteur d'ordres

Les valeurs par défaut correspondent à la formule **Invest Store Intégral** du Crédit Agricole. Elles varient selon les caisses régionales : vérifiez celles de votre caisse.

| Réglage | Par défaut |
|---|---|
| Ordres minimum par an | 12 |
| Frais si l'objectif n'est pas atteint | 96 € |
| Grille de courtage | 0,48 % jusqu'à 500 € · 0,18 % jusqu'à 1 000 € · 0,12 % au-delà |

!> Le taux de la tranche s'applique au **montant total** de l'ordre. Un ordre de 600 € coûte 600 × 0,18 % = 1,08 €, soit moins qu'un ordre de 400 € (1,92 €). Mieux vaut donc passer des ordres d'au moins 500 €.

La grille sert à calculer les frais des ordres, le simulateur, l'estimation sur la fiche d'un titre et les frais aller-retour des prévisions.

## Corrections d'éligibilité

Si un badge d'éligibilité est faux (votre banque accepte ou refuse le titre), corrigez-le ici. Votre correction est **toujours prioritaire** sur la règle automatique et n'est jamais écrasée par les mises à jour.
