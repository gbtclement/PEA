# Documentation admin

Cette documentation s'adresse à la personne qui **installe, fait tourner et fait évoluer** PEA Radar. Elle décrit l'architecture, les calculs exacts, l'API, la base de données et les commandes.

?> Vous cherchez comment **utiliser** l'application ou comprendre la bourse ? C'est le [guide utilisateur](/guide/ ':ignore'), accessible depuis la barre latérale de l'application.

!> Cette documentation n'est pas protégée : elle n'est pas liée dans la navigation, mais toute personne qui connaît l'adresse `/documentation/` peut la lire. C'est acceptable en local. Avant une mise en ligne, il faudra la protéger (voir [SEO et mise en ligne](seo.md)).

## Par où commencer ?

| Vous voulez… | Lisez |
|---|---|
| Installer l'application, la démarrer, la sauvegarder | [Installation et exploitation](installation.md) |
| Comprendre comment les morceaux s'emboîtent | [Architecture](architecture.md) |
| Savoir quand et comment les données sont rafraîchies | [Données et worker](donnees.md) |
| Connaître les formules exactes du score | [Score mixte](score.md) |
| Connaître les calculs des prévisions | [Moteur de prévisions](previsions.md) |
| Modifier le code et lancer les tests | [Développement et tests](developpement.md) |

## En un coup d'œil

```text
Navigateur ─► web (nginx : React, /guide, /documentation) ─► api (FastAPI) ─► db (PostgreSQL 16)
                                                                   ▲
                        worker (tâches planifiées : Yahoo, scores, prévisions) ─┘
```

| Adresse | Contenu |
|---|---|
| http://localhost:8095 | L'application |
| http://localhost:8095/guide/ | Le guide utilisateur |
| http://localhost:8095/documentation/ | Cette documentation admin |
| http://localhost:8000/docs | La doc interactive de l'API (mode développement uniquement) |

Le code source est sur https://github.com/gbtclement/PEA.
