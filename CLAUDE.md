# PEA Radar

Application web personnelle, en local, pour un investisseur débutant qui a un PEA au Crédit Agricole (formule Invest Store Intégral). Elle repère les actions et ETF européens éligibles au PEA, les classe avec un score mixte, suit le portefeuille et le compteur d'ordres annuels, et intègre un assistant Claude.

C'est un outil d'aide à la décision, pas un conseil en investissement : garder cet avertissement partout où l'app recommande quelque chose.

- Spécification : `docs/superpowers/specs/2026-09-26-pea-radar-design.md`. C'est la référence en cas de doute.
- Comptes utilisateurs : `docs/superpowers/specs/2026-09-28-comptes-utilisateurs-design.md` (étapes `comptes-socle`, `comptes-securite`, `comptes-admin` et `comptes-rgpd` faites, suivante : `notifications`).
- Plans des lots : `docs/superpowers/plans/`.
- Utilisateur : francophone et débutant en bourse comme en code. Il lui faut des explications simples, en français.

## Architecture

```
Navigateur ─► web (nginx : SPA React + proxy /api, /robots.txt, /sitemap.xml, /llms.txt) ─► api (FastAPI) ─► db (PostgreSQL 16)
                                                                   worker (APScheduler, même image que api) ─┘
                                                                     └─ SMTP ─► mailpit (local, :8025) ou Brevo (en ligne)
```

**Ports** : web **8095**, API de développement **8000**, Vite **5180**, Mailpit **8025**. Ne pas prendre 8080, 8081 ni 5173, déjà utilisés sur ce PC.

### Backend (`backend/app`)

- **Couches** : `api/routes` → `services` → `repositories` / `providers`.
  - Les services ne connaissent ni HTTP ni Yahoo.
  - Les calculs (indicateurs, score, frais, positions, éligibilité) sont des fonctions pures, testées sans base ni réseau.
- **Contenu des dossiers** :
  - `core/` : configuration (`config.py`, surchargée par variables d'environnement), base de données, `security.py` (Argon2, empreintes de jetons), `current_user.py`.
  - `services/auth/` : comptes, codes et liens par mail, sessions, appareils connus, reprise par l'admin (`bootstrap.py`), Google (`google.py`), Turnstile (`captcha.py`), fuites de mots de passe (`breach.py`). `services/ratelimit.py` (limites anti-abus) et `services/security_log.py` (journal `security_events`). `services/mail/` : rendu des mails et file d'envoi (`enqueue`), envoyée par la tâche `jobs/mail.py` toutes les 5 s.
  - `models/` : SQLAlchemy 2 (API synchrone). Les migrations sont dans `backend/alembic/versions`.
  - `providers/` : `yahoo.py` (yfinance) et `euronext.py`, derrière les interfaces `providers/base.py`.
  - `jobs/` : tâches planifiées du worker :
    - univers à 7 h et historique quotidien à 7 h 30, en semaine ; passage du soir à 18 h 15 (clôtures officielles du jour, puis scores et prévisions) ;
    - cours par paliers T1/T2/T3 (1, 5 et 5 min), en séance seulement ;
    - score après chaque passage T2.
  - `services/scoring/` : le score sur 100, avec 50 points techniques et 50 fondamentaux par défaut. Les maxima sont dans `scoring/config.py`, et les ETF n'ont que la partie technique.
  - `services/forecast/` : prévisions court terme sans API (pandas).
    - `signals.py` : 14 signaux calculés uniquement avec les données disponibles le jour même — **jamais de donnée future** (un test le vérifie).
    - `stats.py` et `predict.py` : statistiques par signal et horizon (1, 5, 21 séances), fiabilité (t de Student corrigé du chevauchement), prédiction pondérée et ramenée vers la moyenne.
    - `engine.py` : calcul complet et test sur l'année écoulée, avec des statistiques d'entraînement limitées aux fenêtres terminées avant la date de coupure.
    - Tâches `jobs/forecasts.py` : statistiques recalculées si elles ont plus de 7 jours (environ 45 s), prédictions du jour et vérification des anciennes chaque matin après l'historique (environ 10 s).
  - `services/eligibility/rules.py` : pays du siège déduit du préfixe ISIN (UE/EEE → éligible, foncières REIT → « à vérifier »). Une correction manuelle (`eligibility_override`) est toujours prioritaire.
  - `services/assistant/` : chat Claude (SDK `anthropic`) avec une boucle d'outils manuelle, en streaming SSE, et le catalogue des modèles et de leurs prix.
  - `seeds/` : CSV de secours (instantané Euronext, ETF, indices, actions hors Euronext).

### Frontend (`frontend/src`)

- **Stack** : React 19, react-router 7, TanStack Query/Table/Virtual, Tailwind 4 et shadcn (`components/ui`, qui importe `cn` depuis le paquet `cn` de shadcn). Graphiques avec Lightweight Charts (fiche d'un titre) et ECharts.
- **Contenu des dossiers** :
  - `features/<domaine>/` contient une page, ses composants et ses tests. `app/` contient le layout, le routeur, le menu du compte et la page 404.
  - `features/auth/` : écrans de compte, `useMe()` (compte connecté ou `null`), `RequireAuth`, qui enveloppe les pages privées dans le routeur, et `RequireAdmin` (page 404 pour un non-admin). `features/settings/` : cartes du compte (profil, mot de passe, adresse, appareils) et frais. `features/admin/` : onglet Admin. Le client HTTP (`lib/api/client.ts`) ajoute l'en-tête `X-CSRF-Token` et transforme les erreurs en `ApiError(status, message, code)`.
  - `lib/api/schema.d.ts` est **généré** depuis l'OpenAPI de l'API (`npm run gen:api`, API de dev lancée). Ne pas l'éditer à la main.
  - `seo/usePageMeta.ts` : chaque page l'appelle pour son titre, sa description, sa canonical et son JSON-LD. Les pages privées passent `noindex: true`.

### Guide et documentation admin (`frontend/public/guide`, `frontend/public/documentation`)

- Deux sites **Docsify** en Markdown, servis par nginx **hors du routeur React** :
  - `/guide/` : guide utilisateur (`app/` une page par écran, `bourse/` cours avec exemples chiffrés), sans nom de fichier ni commande. Lié en bas de la barre latérale par un `<a>` classique, pas un `NavLink` ;
  - `/documentation/` : documentation admin (technique, installation, API, formules), **réservée aux admins** : nginx appelle `GET /api/auth/admin-check` (`auth_request`) avant chaque fichier et renvoie les autres vers `/connexion?suite=%2Fdocumentation%2F`. Liée seulement depuis l'onglet Admin, `noindex`. `/guide/` et `/docsify/` restent publics.
- Docsify, ses plugins, `theme.css` et `back-to-app.js` sont partagés dans `public/docsify/` (pas de CDN, versions dans `VERSIONS.md`). La configuration de chaque site est dans son `config.js` : **aucun script en ligne** (CSP).
- Liens entre pages toujours depuis la racine du site (`bourse/pea.md`), menu dans le `_sidebar.md` de chaque site. Le guide ne renvoie jamais vers la documentation admin. Dans un tableau, écrire `&lt;` au lieu de `<` devant du gras.
- Quand une fonctionnalité change, mettre à jour la page du guide et la page de la documentation admin concernées dans la même branche. `e2e/documentation.spec.ts` vérifie que chaque page des deux sites s'affiche et que les liens internes existent.

## Commandes

Python et Node ne sont pas forcément installés sur l'hôte Windows : le backend se lance **toujours dans Docker**. Si Docker ne répond pas, Docker Desktop est peut-être arrêté.

```bash
# Application complète (http://localhost:8095) — reconstruire après tout changement de code
docker compose up -d --build

# Backend de dev (code monté, rechargement auto, API sur :8000, migrations appliquées au démarrage)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db api worker
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q        # ~600 tests, base pea_radar_test
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api alembic revision --autogenerate -m "..."
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api alembic upgrade head

# Comptes (dans le conteneur api)
docker compose exec -T api python -m app.cli bootstrap-admin            # ADMIN_EMAIL devient admin (lancé au démarrage de l'API)
docker compose exec -T api python -m app.cli ensure-user --email … --password … [--admin]   # compte validé (e2e, dépannage)

# Frontend
cd frontend && npm install
npm run dev          # :5180, proxy /api et fichiers SEO vers :8000
npm test             # Vitest (~190 tests)
npx tsc -b           # vérification des types
npm run build
npm run e2e          # Playwright contre http://localhost:8095 : reconstruire web et api avant (COOKIE_SECURE=false, mails vers Mailpit : si .env vise Brevo, voir docker-compose.e2e.yml)
```

- `pytest` exclut par défaut les tests marqués `network`, qui appellent le vrai Yahoo.
- Le test de bout en bout `layout.spec.ts` vérifie qu'aucune page n'est coupée entre 1100 et 1440 px. `seo.spec.ts` vérifie qu'il y a un seul `h1` par page, les métadonnées et `noindex`. `headers.spec.ts` vérifie les en-têtes de sécurité et l'absence de violation CSP.

## Conventions

- **Langues** :
  - interface, messages d'erreur visibles, commentaires et docstrings en **français** ;
  - identifiants de code en anglais ;
  - messages de commit en anglais, au format conventional commits (`feat:`, `fix:`, `docs:`, `chore:`).
- **Comptes** :
  - toute donnée personnelle (ordres, favoris, conversations, réglages) porte un `user_id` (UUID) ;
  - les routes obtiennent l'utilisateur **uniquement** via `core/current_user.py` : `get_current_user()` (route privée, `401`, et `403 terms_outdated` si les CGU en vigueur ne sont pas acceptées), `get_account_user()` (routes du compte lui-même `/me…`, sans vérifier les CGU), `get_optional_user()` (route publique), `require_admin()` (toutes les routes `/api/admin/*`) ou `require_premium()` (assistant ; un admin est toujours Premium, voir `User.has_premium`) ;
  - les nouvelles erreurs d'API renvoient `{"detail": {"code", "message"}}` ;
  - ne **jamais** stocker un jeton en clair (session, code, lien) : seulement son empreinte (`token_hash`) ;
  - `enqueue()` ne fait jamais de commit, et l'API n'envoie jamais un mail elle-même : c'est le worker ;
  - un compte se supprime **uniquement** par `erase_account()` (`services/privacy/erasure.py`) : titulaire, admin ou inactivité ;
  - les durées de conservation sont dans `services/privacy/retention.py` (tâche nocturne `cleanup`) : toute nouvelle donnée personnelle y reçoit la sienne, et une ligne dans le registre (`frontend/public/documentation/registre.md`) ;
  - changer le texte des CGU oblige à changer `TERMS_VERSION` (`core/terms.py`) et `LEGAL_UPDATED` (`features/legal/content.tsx`).
- **TDD** : écrire le test qui échoue, puis le code.
  - Côté backend, tests d'API avec `client` (connecté), `anon_client` (visiteur) ou `admin_client` (conftest, sur `https://testserver` pour les cookies `Secure`), `sign_in()` dans `tests/auth_helpers.py`, et fabriques dans `tests/factories.py`.
  - Faux fournisseurs dans `tests/fakes.py` (marché), `tests/fake_llm.py` (Claude), `tests/fake_mailer.py` (SMTP), et les fixtures `fake_captcha` (Turnstile), `fake_breach` (Have I Been Pwned) et `fake_google`. Aucun test ne doit appeler Yahoo, Anthropic, un vrai serveur de mail, Google, Cloudflare ni Have I Been Pwned.
- **Mise en page** : thème clair, bureau uniquement. L'app est utilisable dès 1024 px, sur deux colonnes à partir de `xl` (1280 px). Les enfants d'une grille ont besoin de `min-w-0`. Toujours vérifier qu'aucune carte n'est coupée (les cartes shadcn ont `overflow-hidden`).
- **Titres** : un seul `h1` par page. `CardTitle` rend un `h2`, un sous-titre dans une carte est un `h3`.
- **Flux Git** : une branche par lot ou par sujet, et des PR ouvertes avec `gh pr create` (installé et connecté). Dépôt : https://github.com/gbtclement/PEA.

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
- **Secrets** (clé Claude, SMTP, Google, Turnstile, `APP_SECRET`) :
  - uniquement dans `.env` : **jamais en base, jamais renvoyés au navigateur ni écrits dans les logs**. La clé Claude est lue seulement dans `ANTHROPIC_API_KEY` ;
  - l'onglet Admin montre l'état de la configuration (`GET /api/admin/config-status`) en booléens, **jamais les valeurs** ;
  - `.env` n'est pas versionné, seul `.env.example` l'est.
- **Assistant** :
  - réservé aux membres Premium (`require_premium()`) ; `GET /api/assistant/status` dit à l'interface pourquoi il est indisponible (`premium`, `not_configured`, `limit_reached`) ;
  - modèle et limite mensuelle par utilisateur dans `app_settings` (une ligne, lue par `get_app_settings()`, réglée dans l'onglet Admin) ;
  - le coût de chaque réponse s'ajoute dans `ai_usage` par `add_cost()` (utilisateur × mois de Paris) : **jamais recalculé depuis les conversations**, supprimer une conversation ne rend pas de budget ;
  - modèle par défaut `claude-opus-5`, avec `thinking: {type: "adaptive"}`. Le repli serveur en cas de refus n'est activé que pour Opus 5 ;
  - la réponse tourne dans un fil avec sa propre session : elle est toujours enregistrée, même si le navigateur part, et la connexion à Claude est alors coupée ;
  - nginx : `proxy_buffering off` et `proxy_read_timeout 600s` pour le SSE.
- **SEO** :
  - en local, `SEO_INDEXING=false`, donc robots.txt interdit tout. En ligne, passer à `true` et renseigner `PUBLIC_BASE_URL` ;
  - l'API publique doit rester lisible par les robots, car les pages sont rendues dans le navigateur ;
  - le portefeuille, l'assistant, les réglages et les **prévisions** sont toujours en `noindex` (prudence AMF pour les prévisions) et réservés aux membres connectés ;
  - pré-générer les pages publiques à la mise en ligne.
- **Comptes et mails** :
  - la migration `a7c3e9f1b2d4` (identifiants des utilisateurs en UUID) est **à sens unique** : sauvegarder la base (`pg_dump`) avant la première reconstruction qui l'applique. L'API de dev partage le volume `pgdata` et migre au démarrage ;
  - `COOKIE_SECURE=false` seulement en local (HTTP). En ligne, `true`, sinon les sessions voyagent en clair ;
  - `ADMIN_EMAIL` reprend au démarrage le compte « Moi » d'avant les comptes, et reçoit un lien pour choisir son mot de passe ;
  - les routes qui reçoivent une adresse mail répondent pareil qu'un compte existe ou non : ne pas le trahir dans un message ;
  - limites anti-abus dans `ratelimit.LIMITS` : 10 mots de passe faux par adresse en 15 min bloquent le compte 15 min, Turnstile après 3 échecs, plafonds par IP pour la connexion, l'inscription et les mails. Les nouvelles routes publiques de compte prennent `Depends(check_origin)` ;
  - fournisseurs externes : Google (`GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`, vide = pas de bouton), Cloudflare Turnstile (`TURNSTILE_SITE_KEY`/`TURNSTILE_SECRET_KEY`, clé secrète vide = désactivé), Have I Been Pwned (`HIBP_ENABLED`). Tous les trois laissent passer s'ils ne répondent pas ;
  - le contenu des mails à code ou à lien est effacé de `email_log` dès l'envoi : ne jamais y relire un code.
- **En-têtes nginx** (`frontend/nginx/security-headers.conf`, inclus dans `server` et dans tout `location` qui a ses propres `add_header`) : CSP stricte, `X-Frame-Options DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`.
  - **Ne jamais affaiblir la CSP de l'application pour une page de documentation** : au besoin, une CSP propre aux `location` du guide, de `/docsify/` et de `/documentation/`.
  - `HSTS_ENABLED=true` (lu par `web`) seulement une fois le HTTPS en place.
  - Derrière un proxy HTTPS devant nginx, ajouter `set_real_ip_from` / `real_ip_header` : sinon toutes les limites par IP (`client_ip()`, dernière entrée de `X-Forwarded-For`) visent l'IP du proxy.
- **Fuseau** : `Europe/Paris` pour le calendrier de bourse (`services/market_calendar.py`).
