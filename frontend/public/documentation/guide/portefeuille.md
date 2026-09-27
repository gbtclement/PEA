# Portefeuille

PEA Radar n'est pas connecté à votre banque : vous **saisissez vous-même vos ordres**, après les avoir passés sur le site du Crédit Agricole. L'application calcule le reste.

## Saisir un ordre

Bouton **+ Nouvel ordre** sur la page Portefeuille, ou **+ J'ai acheté** sur la fiche d'un titre.

| Champ | Remarque |
|---|---|
| Date | Date d'exécution de l'ordre |
| Sens | Achat ou vente |
| Titre | Recherche par nom, ticker ou ISIN |
| Quantité | Nombre de titres |
| Prix | Prix unitaire d'exécution |
| Frais | **Calculés automatiquement** selon votre grille de courtage ; modifiables si votre relevé indique un autre montant |

Une **vente de plus de titres que vous n'en détenez** à cette date est refusée.

Les ordres se modifient ou se suppriment dans l'**historique des ordres**, en bas de page. Les frais sont recalculés si vous changez le montant.

## Ce que la page affiche

- **Chiffres clés** : valeur totale, montant investi, plus ou moins-value en euros et en pourcentage, variation du jour.
- **Compteur d'ordres** de l'année civile (achats et ventes), avec alerte de rythme.
- **Répartition** par titre et par secteur (graphiques en anneau).
- **Évolution de la valeur** du portefeuille depuis votre premier ordre, reconstituée à partir de vos ordres et des cours de clôture.
- **Positions** : titre, quantité, PRU, cours, valeur, plus ou moins-value.
- **Historique des ordres.**

## Le PRU

Le **prix de revient unitaire** est ce que vous a coûté en moyenne chaque titre encore détenu, **frais d'achat inclus**.

> Exemple : vous achetez 10 actions à 50 € (500 €, frais 0,48 % = 2,40 €), puis 10 à 60 € (600 €, frais 0,18 % = 1,08 €). Vous avez dépensé 1 103,48 € pour 20 titres : le PRU est de 55,17 €.

Une vente ne change pas le PRU des titres restants. Elle dégage une plus ou moins-value **réalisée** : prix de vente moins frais de vente, moins le PRU des titres vendus.

Les calculs sont détaillés dans [Portefeuille et frais](technique/portefeuille.md).
