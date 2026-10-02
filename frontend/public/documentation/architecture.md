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
 Google, Cloudflare, HIBP ◄──────────┘                                     ▲
   Yahoo Finance / Euronext ◄──── worker (APScheduler, même image) ───────┘
                                     │
                                     └─ SMTP ──► mailpit (:8025, en local) ou Brevo (en ligne)
```

Cinq conteneurs Docker Compose :

| Service | Rôle | Technologies |
|---|---|---|
| `web` | Sert l'interface compilée, le guide et la documentation admin, relaie `/api` | nginx 1.27, build Vite |
| `api` | API REST et flux SSE de l'assistant. **Ne contacte pas Yahoo pendant une requête**, sauf pour l'intraday (graphique 1J) et les actualités, mis en cache | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| `worker` | Liste des titres, cours, historique, fondamentaux, scores, prévisions, **envoi des mails** (file `email_log`) | Même image que `api`, APScheduler |
| `db` | Stockage persistant (volume `pgdata`) | PostgreSQL 16 |
| `mailpit` | Capture les mails envoyés en local et les affiche sur http://localhost:8025 | Mailpit |

`api` et `worker` partagent le paquet Python `backend/app`, mais sont deux processus distincts.

### Fournisseurs externes

| Fournisseur | Appelé par | Pour | Si absent ou muet |
|---|---|---|---|
| Yahoo Finance, Euronext | `worker` (et `api` pour l'intraday) | Titres, cours, fondamentaux | Données non rafraîchies |
| Claude (Anthropic) | `api` | Assistant IA | Assistant indisponible |
| SMTP (Mailpit, Brevo) | `worker` | Mails du compte | Mails gardés en file d'attente |
| Google (OpenID Connect) | `api` | « Continuer avec Google » | Bouton masqué si non configuré |
| Cloudflare Turnstile | `api` (vérification), navigateur (widget) | Case anti-robot | Désactivé si non configuré, ignoré si muet 5 s |
| Have I Been Pwned | `api` | Refuser les mots de passe connus dans les fuites | Ignoré après 2 s |

Aucun test n'appelle Google, Cloudflare ni Have I Been Pwned : ils sont remplacés par des faux (voir [Développement et tests](developpement.md)).

### En-têtes de sécurité

nginx ajoute à toutes ses réponses (`frontend/nginx/security-headers.conf`) :

| En-tête | Valeur |
|---|---|
| `Content-Security-Policy` | `default-src 'self'`, scripts de `'self'` et `https://challenges.cloudflare.com` (Turnstile), iframe Turnstile seulement, styles en ligne autorisés, `frame-ancestors 'none'` |
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | Caméra, micro, géolocalisation, paiement et USB interdits |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains`, seulement si `HSTS_ENABLED=true` |

- La configuration nginx est un **modèle** (`frontend/nginx/default.conf.template`) : au démarrage, l'image remplace `${HSTS_ENABLED}`, et seulement les variables `HSTS_*` (`NGINX_ENVSUBST_FILTER`).
- Un `location` qui ajoute son propre `add_header` perd ceux du `server` : il doit inclure `security-headers.conf` à nouveau, comme `/assets/` et `/documentation/`.
- `/documentation/` est réservée aux admins : nginx interroge `GET /api/auth/admin-check` avant chaque fichier (`auth_request`) et renvoie les autres vers `/connexion?suite=%2Fdocumentation%2F`. `/guide/` et `/docsify/` restent publics. Voir [Comptes utilisateurs](comptes.md#documentation-protégée).
- Aucun script en ligne n'est permis : la configuration de Docsify est dans `guide/config.js` et `documentation/config.js`. Ne jamais affaiblir la CSP de l'application pour une page de documentation. `e2e/headers.spec.ts` vérifie les en-têtes et l'absence de violation sur l'application, le guide et la documentation.

## Arborescence

```text
PEA/
├── docker-compose.yml          # les 5 services
├── docker-compose.dev.yml      # surcharge de dev : code monté, --reload, port 8000 exposé
├── .env.example                # modèle de configuration (.env n'est pas versionné)
├── CLAUDE.md                   # contexte pour Claude Code
├── docs/superpowers/           # spécifications et plans de chaque lot
├── backend/
│   ├── alembic/versions/       # migrations de la base
│   ├── app/
│   │   ├── api/routes/         # un fichier par domaine
│   │   ├── core/               # config, base, sécurité (mots de passe, jetons), utilisateur courant
│   │   ├── models/             # tables SQLAlchemy
│   │   ├── schemas/            # entrées/sorties Pydantic
│   │   ├── repositories/       # requêtes SQL
│   │   ├── services/           # logique métier (score, prévisions, frais, portefeuille, assistant…)
│   │   ├── providers/          # Yahoo (yfinance) et Euronext
│   │   ├── jobs/               # tâches du worker, dont l'envoi des mails
│   │   ├── cli.py              # python -m app.cli bootstrap-admin | ensure-user
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
- Les **calculs** (indicateurs, score, frais, positions, enveloppes, signaux) sont des **fonctions pures**, testées sans base ni réseau.
- Les pages ne lisent que la base : les appels externes lents se font dans le worker.

## Plusieurs utilisateurs

- Toute donnée personnelle (ordres, favoris, conversations, réglages) porte un `user_id` (UUID).
- Les routes obtiennent l'utilisateur **uniquement** par les dépendances de `core/current_user.py` : `get_current_user()` pour une route privée (`401` sans session), `get_optional_user()` pour une route publique, `require_admin()` pour une route d'administration. Elles vérifient la session et le jeton CSRF.
- L'API ne fait jamais partir un mail : elle l'ajoute à la file (`enqueue()`), le worker l'envoie.

Voir [Comptes utilisateurs](comptes.md).

## Configuration

Toutes les valeurs sont dans `backend/app/core/config.py` (`Settings`, pydantic-settings) et peuvent être surchargées par une variable d'environnement du même nom en majuscules dans `.env`.

| Variable | Défaut | Rôle |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://pea:pea@db:5432/pea_radar` | Base principale |
| `TEST_DATABASE_URL` | `…/pea_radar_test` | Base des tests (créée par `backend/docker/initdb`) |
| `APP_SECRET` | *(vide)* | Signe les cookies temporaires de la connexion Google (obligatoire pour Google) |
| `ANTHROPIC_API_KEY` | *(vide)* | Clé Claude de l'assistant. Seul endroit où elle est lue ; sans elle, l'assistant est « pas encore configuré » |
| `ASSISTANT_MODEL` | `claude-opus-5` | Modèle de secours si la ligne `app_settings` manque. Le modèle se change dans l'onglet Admin |
| `YAHOO_CHUNK_SIZE` / `YAHOO_PAUSE_SECONDS` | `50` / `1.0` | Taille des paquets et pause entre deux requêtes Yahoo |
| `TIER2_SIZE` | `150` | Nombre de titres du palier T2 |
| `QUOTES_T1_MINUTES` / `T2` / `T3` | `2` / `5` / `30` | Fréquence des cours par palier |
| `MIN_TURNOVER_EUR` | `500000` | Montant moyen échangé minimum pour être « liquide » |
| `MIN_HISTORY_DAYS` | `200` | Séances minimum pour entrer dans le top 10 |
| `MIN_AVAILABLE_RATIO` | `0.6` | Part minimum des points du score calculables pour le top 10 |
| `SEO_INDEXING` | `false` | Voir [SEO et mise en ligne](seo.md) |
| `PUBLIC_BASE_URL` | `http://localhost:8095` | Adresse publique du site, utilisée aussi pour les liens des mails |
| `ADMIN_EMAIL` | *(vide)* | Compte administrateur, qui reprend les données d'avant les comptes |
| `COOKIE_SECURE` | `true` | `false` seulement en local sans HTTPS |
| `SESSION_DAYS` / `SESSION_SHORT_HOURS` | `30` / `12` | Durée d'une session avec et sans « Rester connecté » |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | *(vide)* / `587` / *(vide)* / *(vide)* | Serveur d'envoi des mails |
| `SMTP_TLS` | `starttls` | `starttls`, `ssl` ou `none` (Mailpit) |
| `MAIL_FROM` | `Cotalyx <no-reply@localhost>` | Expéditeur des mails |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | *(vide)* | Client OAuth Google ; vide = pas de bouton Google |
| `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET_KEY` | *(vide)* | Cloudflare Turnstile ; clé secrète vide = captcha désactivé |
| `HIBP_ENABLED` | `true` | Refus des mots de passe connus dans les fuites |
| `DEV_ORIGINS` | `http://localhost:5180` | Origines acceptées en plus de `PUBLIC_BASE_URL`, séparées par des virgules |
| `HSTS_ENABLED` | `false` | Lu par `web` (nginx) : envoie l'en-tête HSTS. `true` seulement derrière HTTPS |

## Ports

| Port | Usage |
|---|---|
| **8095** | Application complète (nginx) |
| **8000** | API en mode développement (`docker-compose.dev.yml`), avec la doc interactive de l'API sur `/docs` |
| **5180** | Serveur Vite en développement |
| **8025** | Mailpit : les mails envoyés en local |

?> 8080, 8081 et 5173 sont volontairement évités : ils sont déjà utilisés par d'autres projets sur le PC de développement.
