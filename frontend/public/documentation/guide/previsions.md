# Prévisions

La page **Prévisions** (`/previsions`) estime ce que pourrait faire chaque action à **1 jour, 1 semaine et 1 mois**, à partir de ce qui s'est passé dans le passé après des situations similaires. Elle ne fait appel à aucune API d'IA : ce sont des statistiques sur 5 ans d'historique.

!> Ce sont des **estimations statistiques, pas des certitudes ni des conseils**. Même un signal « fiable » se trompe souvent : une probabilité de hausse de 58 % veut dire que la baisse arrive 42 fois sur 100.

## Le principe en 3 phrases

1. Chaque jour, on repère sur chaque action des **signaux techniques** connus : cassure d'un plus haut, forte baisse sur la semaine, croisement de moyennes…
2. Pour chaque signal, on a mesuré sur 5 ans ce qui a suivi ses apparitions : combien de fois le cours a monté, de combien en moyenne, et s'il a fait mieux que le CAC 40.
3. La prévision d'une action combine les statistiques de ses signaux actifs.

Une action sans signal actif aujourd'hui n'a pas de prévision. Le détail des calculs est dans [Moteur de prévisions](technique/previsions.md).

## Les trois onglets

Le choix de l'onglet est gardé dans l'adresse (`?vue=…`).

### Prédictions

Un tableau de toutes les actions qui ont au moins un signal aujourd'hui :

- le titre, son cours et ses signaux actifs ;
- pour chaque horizon (1 j, 1 sem, 1 mois) : le **gain attendu** et la **probabilité de hausse** ;
- la **fiabilité** : élevée, moyenne ou faible.

Vous pouvez trier par gain attendu (1 semaine par défaut), par probabilité ou par fiabilité, et filtrer par nom, éligibilité PEA (cochée par défaut), sens (hausse ou baisse) et fiabilité minimale.

### Statistiques des signaux

Pour l'horizon choisi, chacun des 14 signaux avec :

| Colonne | Signification |
|---|---|
| Cas | Nombre de fois où le signal est apparu sur une action liquide en 5 ans |
| % de hausses | Part des cas où le cours a monté ensuite |
| Gain moyen / médian | Ce qu'on aurait gagné en moyenne / dans le cas « du milieu » |
| Après frais | Part des cas qui ont gagné plus que les frais aller-retour (≈ 0,96 % pour 500 €) |
| % au-dessus du CAC 40 | Part des cas qui ont fait mieux que l'indice sur la même période |
| Fiabilité | Le résultat se distingue-t-il vraiment du hasard ? |

La ligne **« Toutes les actions (référence) »** reste en haut : c'est ce qu'on obtient en achetant n'importe quelle action liquide, n'importe quel jour. Un signal n'est intéressant que s'il fait **nettement mieux que cette référence**.

?> Le « sens » (hausse ou baisse) d'un signal est l'intuition courante. Les statistiques montrent parfois l'inverse : c'est ce qui s'est réellement passé qui compte.

### Bulletin de notes

Deux façons de vérifier si les prévisions valent quelque chose :

- **Test sur l'année écoulée.** Les statistiques sont recalculées **sans** la dernière année. Puis, pour chaque jour de cette année, on prend les 10 meilleures prévisions de hausse et on regarde ce qui s'est vraiment passé, comparé à toutes les actions les mêmes jours. Une phrase résume le verdict.
- **Suivi réel.** Chaque matin, les prévisions du jour sont enregistrées, puis vérifiées automatiquement quand l'horizon est atteint. Ce suivi démarre vide et se remplit avec le temps.

## Sur la fiche d'un titre

La carte **Prévisions court terme** montre les signaux actifs du titre et ses trois horizons, avec un lien vers cette page.

## Quand sont-elles mises à jour ?

- Chaque matin de semaine vers 7 h 30, après le chargement des cours de clôture de la veille. Les prévisions portent donc sur la **dernière séance terminée**.
- Les statistiques des signaux sont recalculées une fois par semaine.
