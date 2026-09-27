# Score mixte

Code : `backend/app/services/scoring/` (fonctions pures), calcul planifié dans `backend/app/jobs/scoring.py`.

Chaque titre reçoit un score **sur 100** : **50 points techniques** (le comportement du cours) et **50 points fondamentaux** (la santé de l'entreprise). Il est recalculé après chaque passage T2, donc environ toutes les 5 minutes en séance, après l'historique quotidien (7 h 30 et 18 h 15) et, au démarrage, une fois les fondamentaux chargés.

?> Le score sert à **trier et expliquer**, pas à prédire. Chaque composant produit une phrase en français, affichée telle quelle dans l'interface.

## Partie technique (50 points)

| Composant | Max | Règle |
|---|---|---|
| **Tendance** | 20 | cours > MM50 : +7 · cours > MM200 : +7 · MM50 > MM200 : +6 |
| **Dynamique 3 mois** | 15 | performance sur 3 mois moins celle du CAC 40 : de −10 points de % (0 pt) à +10 points de % (15 pts), linéaire et bornée |
| **RSI 14** | 10 | 40–60 → 10 · 30–40 ou 60–70 → 6 · < 30 → 4 · > 70 → 0 |
| **MACD (12, 26, 9)** | 5 | croisement haussier dans les 5 dernières séances → 5 · MACD au-dessus du signal → 3 · sinon 0 |

## Partie fondamentale (50 points)

| Composant | Max | Règle |
|---|---|---|
| **Valorisation** | 15 | PER ≤ 0,8 × médiane du secteur → 15, linéaire jusqu'à 1,5 × médiane → 0 · PER négatif (entreprise en perte) → 0 |
| **Croissance** | 15 | croissance du BPA (7,5) + croissance du chiffre d'affaires (7,5) : de 0 % (0 pt) à ≥ 15 % (7,5 pts), linéaire |
| **Solidité** | 10 | dette / capitaux propres : ≤ 0,5 → 5, linéaire jusqu'à 2 → 0 · marge nette : de 0 % (0) à ≥ 10 % (5), linéaire |
| **Dividende** | 10 | 0 % → 0, linéaire jusqu'à 2 % → 10 · 2–6 % → 10 · 6–8 % → 7 · > 8 % → 5 (rendement suspect) |

Les maxima sont dans `scoring/config.py` (`MAX_POINTS`). Modifier une valeur met le composant à l'échelle automatiquement.

## Données manquantes

- Un composant sans donnée est **exclu** : le total est ramené sur 100 au prorata des points disponibles.
- `available_ratio` = points calculables / points possibles. S'il est inférieur à 1, le score porte le badge **« données incomplètes »**.
- Sous `MIN_AVAILABLE_RATIO` (60 %), le titre est exclu du top 10.

## ETF

Pas de partie fondamentale : le score est **uniquement technique**, ramené sur 100.

## Entrée dans le top 10

Tous les titres ont un score, visible dans l'Explorer. Pour entrer dans le top 10, il faut en plus :

- type `stock` et éligibilité **confirmée** (`eligible`, automatique ou corrigée) ;
- montant moyen échangé sur 20 séances ≥ `MIN_TURNOVER_EUR` (500 000 €) ;
- au moins `MIN_HISTORY_DAYS` (200) séances d'historique ;
- `available_ratio` ≥ 0,6.

À score égal, le titre le plus liquide passe devant.

## Indicateurs

`backend/app/services/indicators.py` : SMA, EMA, RSI (lissage de Wilder), MACD et performances sur une période. Ces mêmes fonctions alimentent le graphique de la fiche d'un titre et les outils de l'assistant.
