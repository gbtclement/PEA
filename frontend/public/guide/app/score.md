# Comprendre le score

Chaque action reçoit une **note sur 100**. Elle combine deux regards :

- **50 points techniques** : comment se comporte le **cours** (tendance, dynamique) ;
- **50 points fondamentaux** : comment va l'**entreprise** (prix, croissance, solidité, dividende).

Chaque composante s'accompagne d'une phrase : ✅ point fort, ⚠️ point d'attention, ❌ point faible.

## Les 8 composantes

| Composante | Max | Ce qui rapporte des points |
|---|---|---|
| **Tendance** | 20 | Le cours est au-dessus de ses moyennes 50 et 200 jours, et la moyenne 50 est au-dessus de la 200 : la tendance est haussière |
| **Dynamique 3 mois** | 15 | L'action a fait mieux que le CAC 40 sur les 3 derniers mois |
| **RSI** | 10 | L'action n'a ni trop monté (surchauffe) ni trop baissé récemment : RSI entre 40 et 60 |
| **MACD** | 5 | La dynamique vient de repartir à la hausse |
| **Valorisation** | 15 | L'action n'est pas chère par rapport aux autres entreprises de son secteur (PER plus bas que la moyenne) |
| **Croissance** | 15 | Les bénéfices et le chiffre d'affaires progressent (jusqu'à +15 % par an pour le maximum) |
| **Solidité** | 10 | Peu de dette et de bonnes marges |
| **Dividende** | 10 | Un dividende entre 2 % et 6 % par an (au-delà de 8 %, c'est souvent suspect) |

Le vocabulaire est expliqué dans [Lire un graphique](bourse/analyse-technique.md) et [Juger une entreprise](bourse/analyse-fondamentale.md).

## Exemple

| Composante | Points |
|---|---|
| Tendance | 20 / 20 ✅ |
| Dynamique 3 mois | 9 / 15 ✅ |
| RSI | 10 / 10 ✅ |
| MACD | 3 / 5 ✅ |
| **Technique** | **42 / 50** |
| Valorisation | 6 / 15 ⚠️ |
| Croissance | 10 / 15 ✅ |
| Solidité | 7 / 10 ✅ |
| Dividende | 10 / 10 ✅ |
| **Fondamental** | **33 / 50** |
| **Score** | **75 / 100** |

Lecture : une action en bonne forme, dans une entreprise en croissance et solide, mais un peu chère.

## Quand il manque des données

Une composante sans information est retirée du calcul, et le score est ramené sur 100 avec ce qui reste. Le badge **« données incomplètes »** apparaît alors.

> Même exemple, mais sans information sur le dividende : l'action obtient 65 points sur 90 possibles, soit un score de **72 / 100**, avec le badge.

Une action dont moins de 60 % des points sont calculables n'entre pas dans le top 10.

## ETF

Un ETF n'a pas de bénéfices ni de dette : seule la partie technique compte, ramenée sur 100.

## Quand est-il recalculé ?

Environ **toutes les 5 minutes** pendant la séance, puis le soir à 18 h 15 avec les cours de clôture officiels.

!> Le score résume la situation **actuelle**. Il ne dit pas si l'action va monter : une action à 85 peut baisser, une action à 40 peut rebondir.
