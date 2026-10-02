# Prévisions

La page **Prévisions** estime ce que pourrait faire chaque action à **1 jour, 1 semaine et 1 mois**, à partir de ce qui s'est passé dans le passé après des situations similaires. Ce sont des statistiques sur 5 ans d'historique, sans intelligence artificielle.

!> Ce sont des **estimations statistiques, pas des certitudes ni des conseils**. Même un signal « fiable » se trompe souvent : une probabilité de hausse de 58 % veut dire que la baisse arrive 42 fois sur 100.

## Le principe

1. Chaque jour, l'application repère sur chaque action des **signaux** connus des investisseurs : le cours dépasse son plus haut du mois, l'action a chuté de 10 % en une semaine, deux moyennes mobiles se croisent…
2. Pour chaque signal, elle a mesuré sur 5 ans ce qui a suivi ses apparitions : combien de fois le cours a monté, de combien en moyenne, et s'il a fait mieux que le CAC 40.
3. La prévision d'une action combine les statistiques des signaux qu'elle présente aujourd'hui.

Une action sans signal aujourd'hui n'a pas de prévision.

> **Exemple :** une action présente le signal « Cassure du plus haut 20 jours ». Historiquement, sur des milliers de cas, ce signal a été suivi d'une hausse sur une semaine dans 55 % des cas, pour un gain moyen de +0,6 %. La prévision affichera environ +0,6 % à 1 semaine et 55 % de probabilité de hausse. En moyenne, ce n'est pas énorme, et une fois sur deux ou presque, le cours baisse.

## Les trois onglets

### Prédictions

?> Cet onglet est réservé aux membres **[Premium](app/premium.md)**. Sans Premium, la page s'ouvre sur le **Bulletin de notes** ; les statistiques des signaux et le bulletin restent ouverts à tous les membres.

Toutes les actions qui présentent au moins un signal aujourd'hui. Pour chacune :
- ses signaux actifs ;
- pour 1 jour, 1 semaine et 1 mois : le **gain attendu** et la **probabilité de hausse** ;
- la **fiabilité** (élevée, moyenne ou faible) : le résultat se distingue-t-il vraiment du hasard ?

Vous pouvez trier les colonnes et filtrer par nom, enveloppes (case « Mes enveloppes uniquement », cochée par défaut si vous en avez choisi dans vos Réglages), sens (hausse ou baisse) et fiabilité minimale.

### Statistiques des signaux

Les 14 signaux, avec pour l'horizon choisi :

| Colonne | Signification |
|---|---|
| Cas | Nombre de fois où le signal est apparu en 5 ans |
| % de hausses | Part des cas où le cours a monté ensuite |
| Gain moyen / médian | Gain moyen, et gain du cas « du milieu » (moins sensible aux cas extrêmes) |
| Après frais | Part des cas qui ont gagné plus que les frais d'achat et de revente (environ 0,96 % pour 500 €) |
| % au-dessus du CAC 40 | Part des cas qui ont fait mieux que l'indice |
| Fiabilité | Le résultat se distingue-t-il vraiment du hasard ? |

La ligne **« Toutes les actions (référence) »** reste en haut : c'est ce qu'on obtient en achetant n'importe quelle action, n'importe quel jour. **Un signal n'est intéressant que s'il fait nettement mieux que cette référence.**

?> Certains signaux réputés « haussiers » ont en réalité été suivis de baisses, et inversement. C'est ce qui s'est vraiment passé qui compte, pas l'intuition.

### Bulletin de notes

Deux façons de vérifier si les prévisions valent quelque chose :

- **Test sur l'année écoulée** : l'application fait comme si on était il y a un an. Elle prédit chaque jour avec les seules informations de l'époque, choisit les 10 meilleures prévisions de hausse, et regarde ce qui s'est vraiment passé. Une phrase résume le verdict.
- **Suivi réel** : les prévisions de chaque jour sont enregistrées, puis vérifiées quand leur échéance arrive. Ce suivi démarre vide et se remplit avec le temps.

## Sur la fiche d'un titre

La carte **Prévisions court terme** montre les signaux du titre et ses trois horizons. Elle est réservée aux membres [Premium](app/premium.md).

## Quand sont-elles calculées ?

Chaque soir de semaine vers **18 h 15**, avec les cours de clôture de la séance, puis de nouveau le lendemain à 7 h 30. Elles portent toujours sur la **dernière séance terminée**.
