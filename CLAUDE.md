# PEA Radar

Application web personnelle, en local, pour un investisseur débutant qui a un PEA au Crédit Agricole (formule Invest Store Intégral). Elle repère les actions et ETF européens éligibles au PEA, les classe avec un score mixte, suit le portefeuille et le compteur d'ordres annuels, et intègre un assistant Claude.

C'est un outil d'aide à la décision, pas un conseil en investissement : garder cet avertissement partout où l'app recommande quelque chose.

- Spécification : `docs/superpowers/specs/2026-09-26-pea-radar-design.md`. C'est la référence en cas de doute.
- Plans des lots 1 à 5 : `docs/superpowers/plans/`.
- Utilisateur : francophone et débutant en bourse comme en code. Il lui faut des explications simples, en français.

## Architecture

```
Navigateur ─► web (nginx : SPA React + proxy /api, /robots.txt, /sitemap.xml, /llms.txt) ─► api (FastAPI) ─► db (PostgreSQL 16)
                                                                   worker (APScheduler, même image que api) ─┘
```

**Ports** : web **8095**, API de développement **8000**, Vite **5180**. Ne pas prendre 8080, 8081 ni 5173, déjà utilisés sur ce PC.

### Backend (`backend/app`)

- **Couches** : `api/routes` → `services` → `repositories` / `providers`.
  - Les services ne connaissent ni HTTP ni Yahoo.
  - Les calculs (indicateurs, score, frais, positions, éligibilité) sont des fonctions pures, testées sans base ni réseau.
- **Contenu des dossiers** :
  - `core/` : configuration (`config.py`, surchargée par variables d'environnement), base de données, `current_user.py`.
  - `models/` : SQLAlchemy 2 (API synchrone). Les migrations sont dans `backend/alembic/versions`.
  - `providers/` : `yahoo.py` (yfinance) et `euronext.py`, derrière les interfaces `providers/base.py`.
  - `jobs/` : tâches planifiées du worker :
    - univers à 7 h et historique quotidien à 7 h 30, en semaine ;
    - cours par paliers T1/T2/T3 (2, 5 et 30 min), en séance seulement ;
    - score après chaque passage T2.
  - `services/scoring/` : le score sur 100, avec 50 points techniques et 50 fondamentaux par défaut. Les maxima sont dans `scoring/config.py`, et les ETF n'ont que la partie technique.
  - `services/eligibility/rules.py` : pays du siège déduit du préfixe ISIN (UE/EEE → éligible, foncières REIT → « à vérifier »). Une correction manuelle (`eligibility_override`) est toujours prioritaire.
  - `services/assistant/` : chat Claude (SDK `anthropic`) avec une boucle d'outils manuelle, en streaming SSE, et le catalogue des modèles et de leurs prix.
  - `seeds/` : CSV de secours (instantané Euronext, ETF, indices, actions hors Euronext).

### Frontend (`frontend/src`)

- **Stack** : React 19, react-router 7, TanStack Query/Table/Virtual, Tailwind 4 et shadcn (`components/ui`, qui importe `cn` depuis le paquet `cn` de shadcn). Graphiques avec Lightweight Charts (fiche d'un titre) et ECharts.
- **Contenu des dossiers** :
  - `features/<domaine>/` contient une page, ses composants et ses tests. `app/` contient le layout, le routeur et la page 404.
  - `lib/api/schema.d.ts` est **généré** depuis l'OpenAPI de l'API (`npm run gen:api`, API de dev lancée). Ne pas l'éditer à la main.
  - `seo/usePageMeta.ts` : chaque page l'appelle pour son titre, sa description, sa canonical et son JSON-LD. Les pages privées passent `noindex: true`.

## Commandes

Python et Node ne sont pas forcément installés sur l'hôte Windows : le backend se lance **toujours dans Docker**. Si Docker ne répond pas, Docker Desktop est peut-être arrêté.

```bash
# Application complète (http://localhost:8095) — reconstruire après tout changement de code
docker compose up -d --build

# Backend de dev (code monté, rechargement auto, API sur :8000, migrations appliquées au démarrage)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db api worker
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q        # ~315 tests, base pea_radar_test
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api alembic revision --autogenerate -m "..."
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api alembic upgrade head

# Frontend
cd frontend && npm install
npm run dev          # :5180, proxy /api et fichiers SEO vers :8000
npm test             # Vitest (~100 tests)
npx tsc -b           # vérification des types
npm run build
npm run e2e          # Playwright contre http://localhost:8095 : reconstruire web et api avant
```

- `pytest` exclut par défaut les tests marqués `network`, qui appellent le vrai Yahoo.
- Le test de bout en bout `layout.spec.ts` vérifie qu'aucune page n'est coupée entre 1100 et 1440 px. `seo.spec.ts` vérifie qu'il y a un seul `h1` par page, les métadonnées et `noindex`.

## Conventions

- **Langues** :
  - interface, messages d'erreur visibles, commentaires et docstrings en **français** ;
  - identifiants de code en anglais ;
  - messages de commit en anglais, au format conventional commits (`feat:`, `fix:`, `docs:`, `chore:`).
- **Multi-utilisateur prêt** : toute donnée personnelle (ordres, favoris, conversations, réglages) porte un `user_id`. Les routes obtiennent l'utilisateur **uniquement** via `get_current_user()` (`core/current_user.py`), qui renvoie pour l'instant l'utilisateur par défaut.
- **TDD** : écrire le test qui échoue, puis le code.
  - Côté backend, tests d'API avec `client` (conftest) et fabriques dans `tests/factories.py`.
  - Faux fournisseurs dans `tests/fakes.py` (marché) et `tests/fake_llm.py` (Claude). Aucun test ne doit appeler Yahoo ni Anthropic.
- **Mise en page** : thème clair, bureau uniquement. L'app est utilisable dès 1024 px, sur deux colonnes à partir de `xl` (1280 px). Les enfants d'une grille ont besoin de `min-w-0`. Toujours vérifier qu'aucune carte n'est coupée (les cartes shadcn ont `overflow-hidden`).
- **Titres** : un seul `h1` par page. `CardTitle` rend un `h2`, un sous-titre dans une carte est un `h3`.
- **Flux Git** : une branche par lot ou par sujet, et des PR ouvertes par l'utilisateur via des liens GitHub `compare` préremplis (`gh` n'est pas installé). Dépôt : https://github.com/gbtclement/PEA.

## Points d'attention

- **Éligibilité PEA** :
  - il n'existe pas de liste officielle complète, l'univers est reconstruit (Euronext + grands indices + PEA-PME + ETF de `seeds/`) ;
  - l'éligibilité est une déduction, à présenter comme telle ;
  - **ne jamais scraper le Crédit Agricole** (connexion bancaire, conditions d'utilisation).
- **Yahoo (yfinance)** : source gratuite, non officielle et limitée en débit.
  - Respecter les pauses (`yahoo_pause_seconds`, `fundamentals_pause_seconds`) et les paquets de `yahoo_chunk_size` titres.
  - Les tâches lourdes passent par `HEAVY_JOBS_LOCK`.
  - Les cours sont différés, pas du temps réel.
- **Frais et compteur** :
  - grille de courtage Invest Store Intégral : 0,48 % jusqu'à 500 €, 0,18 % jusqu'à 1 000 €, 0,12 % au-delà ;
  - le taux de la tranche s'applique au montant total de l'ordre ;
  - moins de 12 ordres par an coûtent environ 96 € ;
  - tout est modifiable dans les Réglages (`services/fees.py`).
- **Score** : il sert à trier et à expliquer, pas à prédire.
  - Le top 10 exclut les titres peu liquides (`min_turnover_eur`), à l'historique trop court (< 200 jours) ou non confirmés éligibles.
  - Chaque composante renvoie un message lisible, affiché tel quel dans l'interface.
- **Clé API Claude** :
  - elle est chiffrée en base (Fernet, clé dérivée de `APP_SECRET`) ou lue dans `ANTHROPIC_API_KEY` ;
  - **jamais renvoyée au navigateur ni écrite dans les logs** ;
  - changer `APP_SECRET` rend la clé enregistrée illisible ;
  - `.env` n'est pas versionné, seul `.env.example` l'est.
- **Assistant** :
  - modèle par défaut `claude-opus-5`, avec `thinking: {type: "adaptive"}`. Le repli serveur en cas de refus n'est activé que pour Opus 5 ;
  - la réponse tourne dans un fil avec sa propre session : elle est toujours enregistrée, même si le navigateur part, et la connexion à Claude est alors coupée ;
  - nginx : `proxy_buffering off` et `proxy_read_timeout 600s` pour le SSE.
- **SEO** :
  - en local, `SEO_INDEXING=false`, donc robots.txt interdit tout. En ligne, passer à `true` et renseigner `PUBLIC_BASE_URL` ;
  - l'API publique doit rester lisible par les robots, car les pages sont rendues dans le navigateur ;
  - le portefeuille, l'assistant et les réglages sont toujours en `noindex` ;
  - pré-générer les pages publiques à la mise en ligne.
- **Fuseau** : `Europe/Paris` pour le calendrier de bourse (`services/market_calendar.py`).
