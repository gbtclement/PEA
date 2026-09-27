# PEA Radar

PEA Radar est une application web personnelle, lancée en local avec Docker, pour :

- **repérer** les actions et ETF européens éligibles au PEA ;
- les **classer** avec un score sur 100 qui explique ses raisons ;
- consulter des **prévisions court terme** fondées sur des statistiques historiques ;
- **suivre son portefeuille** et le compteur d'ordres annuels de la formule Invest Store Intégral du Crédit Agricole ;
- **poser des questions** à un assistant IA (Claude) qui consulte les données de l'application.

!> PEA Radar est un **outil d'aide à la décision et d'apprentissage**, pas un conseil en investissement. Les cours viennent de Yahoo Finance, avec quelques minutes de retard. Les scores et prévisions sont des estimations, jamais des certitudes.

## Par où commencer ?

| Vous voulez… | Lisez |
|---|---|
| Lancer l'application pour la première fois | [Démarrer](guide/demarrer.md) |
| Comprendre une page de l'application | Le **Guide d'utilisation**, dans le menu à gauche |
| Savoir ce que veut dire PRU, RSI, MACD, ETF… | [Lexique et questions fréquentes](guide/lexique.md) |
| Comprendre comment est calculé le score | [Score mixte](technique/score.md) |
| Comprendre comment sont faites les prévisions | [Moteur de prévisions](technique/previsions.md) |
| Modifier le code | [Architecture](technique/architecture.md) puis [Développement et tests](technique/developpement.md) |

## En un coup d'œil

```text
Navigateur ─► web (nginx : interface React + /documentation) ─► api (FastAPI) ─► db (PostgreSQL 16)
                                                                      ▲
                               worker (tâches planifiées : Yahoo, scores, prévisions) ─┘
```

- **Adresse de l'application :** http://localhost:8095
- **Adresse de cette documentation :** http://localhost:8095/documentation/
- **Code source :** https://github.com/gbtclement/PEA

Utilisez la recherche en haut à gauche pour trouver un mot dans toute la documentation.
