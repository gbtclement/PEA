# Architecture

## Vue d'ensemble

```text
                     ┌────────────────────────────────────────────┐
Navigateur ────────► │ web  (nginx)                               │
  :8095              │  /               → interface React (SPA)   │
                     │  /guide/         → guide utilisateur       │
                     │  /documentation/ → documentation admin     │
                     │  /api/*          → proxy vers api          │
                     │  /robots.txt, /sitemap.xml, /llms.txt → api│
                     └──────────────────────┬─────────────────────┘
                                            ▼
            Claude API ◄──────────── api (FastAPI, :8000) ─────────► db (PostgreSQL 16)
                                                                          ▲
   Yahoo Finance / Euronext ◄──── worker (APScheduler, même image) ───────┘
```

Quatre conteneurs Docker Compose :

| Service | Rôle | Technologies |
|---|---|---|
| `web` | Sert l'interface compilée, le guide et la documentation admin, relaie `/api` | nginx 1.27, build Vite |
| `api` | API REST et flux SSE de l'assistant. **Ne contacte pas Yahoo pendant une requête**, sauf pour l'intraday (graphique 1J) et les actualités, mis en cache | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| `worker` | Liste des titres, cours, historique, fondamentaux, scores, prévisions | Même image que `api`, APScheduler |
| `db` | Stockage persistant (volume `pgdata`) | PostgreSQL 16 |

`api` et `worker` partagent le paquet Python `backend/app`, mais sont deux processus distincts.

## Arborescence

```text
PEA/
├── docker-compose.yml          # les 4 services
├── docker-compose.dev.yml      # surcharge de dev : code monté, --reload, port 8000 exposé
├── .env.example                # modèle de configuration (.env n'est pas versionné)
├── CLAUDE.md                   # contexte pour Claude Code
├── docs/superpowers/           # spécifications et plans de chaque lot
├── backend/
│   ├── alembic/versions/       # migrations de la base
│   ├── app/
│   │   ├── api/routes/         # un fichier par domaine
│   │   ├── core/               # config, base, utilisateur courant
│   │   ├── models/             # tables SQLAlchemy
│   │   ├── schemas/            # entrées/sorties Pydantic
│   │   ├── repositories/       # requêtes SQL
│   │   ├── services/           # logique métier (score, prévisions, frais, portefeuille, assistant…)
│   │   ├── providers/          # Yahoo (yfinance) et Euronext
│   │   ├── jobs/               # tâches du worker
│   │   └── seeds/              # CSV de départ et de secours
│   └── tests/
└── frontend/
    ├── public/guide/           # guide utilisateur (Docsify)
    ├── public/documentation/   # documentation admin (Docsify)
    ├── public/docsify/         # Docsify et plugins partagés
    ├── e2e/                    # tests Playwright
    └── src/
        ├── app/                # layout, barre latérale, routeur, page 404
        ├── components/         # composants partagés, ui/ (shadcn), charts/
        ├── features/<domaine>/ # une page, ses composants et ses tests
        ├── lib/api/            # client HTTP et types générés depuis l'OpenAPI
        └── seo/                # métadonnées par page
```

## Règles de dépendance du backend

```text
api/routes  ──►  services  ──►  repositories (SQL)
                     │
                     └──────►  providers (Yahoo, Euronext) via les interfaces de providers/base.py
```

- Les **services** ne connaissent ni HTTP ni Yahoo.
- Les **calculs** (indicateurs, score, frais, positions, éligibilité, signaux) sont des **fonctions pures**, testées sans base ni réseau.
- Les pages ne lisent que la base : les appels externes lents se font dans le worker.

## Prêt pour plusieurs utilisateurs

- Toute donnée personnelle (ordres, favoris, conversations, réglages) porte un `user_id`.
- Les routes obtiennent l'utilisateur **uniquement** par la dépendance `get_current_user()` (`core/current_user.py`). Elle renvoie aujourd'hui l'utilisateur par défaut. Demain, elle pourra vérifier une session sans modifier les routes.

## Configuration

Toutes les valeurs sont dans `backend/app/core/config.py` (`Settings`, pydantic-settings) et peuvent être surchargées par une variable d'environnement du même nom en majuscules dans `.env`.

| Variable | Défaut | Rôle |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://pea:pea@db:5432/pea_radar` | Base principale |
| `TEST_DATABASE_URL` | `…/pea_radar_test` | Base des tests (créée par `backend/docker/initdb`) |
| `APP_SECRET` | *(vide)* | Chiffre la clé API Claude en base. **À définir, puis ne plus changer.** |
| `ANTHROPIC_API_KEY` | *(vide)* | Clé Claude optionnelle (sinon saisie dans les Réglages) |
| `ASSISTANT_MODEL` | `claude-opus-5` | Modèle par défaut de l'assistant |
| `HISTORY_YEARS` | `5` | Profondeur de l'historique journalier |
| `YAHOO_CHUNK_SIZE` / `YAHOO_PAUSE_SECONDS` | `50` / `1.0` | Taille des paquets et pause entre deux requêtes Yahoo |
| `TIER2_SIZE` | `150` | Nombre de titres du palier T2 |
| `QUOTES_T1_MINUTES` / `T2` / `T3` | `2` / `5` / `30` | Fréquence des cours par palier |
| `MIN_TURNOVER_EUR` | `500000` | Montant moyen échangé minimum pour être « liquide » |
| `MIN_HISTORY_DAYS` | `200` | Séances minimum pour entrer dans le top 10 |
| `MIN_AVAILABLE_RATIO` | `0.6` | Part minimum des points du score calculables pour le top 10 |
| `SEO_INDEXING` | `false` | Voir [SEO et mise en ligne](seo.md) |
| `PUBLIC_BASE_URL` | `http://localhost:8095` | Adresse publique du site |

## Ports

| Port | Usage |
|---|---|
| **8095** | Application complète (nginx) |
| **8000** | API en mode développement (`docker-compose.dev.yml`), avec la doc interactive de l'API sur `/docs` |
| **5180** | Serveur Vite en développement |

?> 8080, 8081 et 5173 sont volontairement évités : ils sont déjà utilisés par d'autres projets sur le PC de développement.
