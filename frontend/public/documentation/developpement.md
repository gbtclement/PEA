# Développement et tests

?> Python n'a pas besoin d'être installé sur le PC : le backend se lance et se teste **toujours dans Docker**. Si Docker ne répond pas, Docker Desktop est sans doute arrêté.

## Application complète

```bash
docker compose up -d --build    # http://localhost:8095 — à relancer après tout changement de code
```

## Backend en mode développement

Le code est monté dans le conteneur, l'API redémarre à chaque modification et elle est exposée sur le port 8000.

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db api worker
```

### Tests backend

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q
```

- Environ 520 tests, sur une base séparée `pea_radar_test`.
- Les tests marqués `network` (qui appellent le vrai Yahoo) sont exclus par défaut.
- Fixtures : le client de test est dans `tests/conftest.py`, les fabriques de données dans `tests/factories.py`.
- Faux fournisseurs : `tests/fakes.py` (marché), `tests/fake_llm.py` (Claude) et `tests/fake_mailer.py` (`FakeMailer`, SMTP). Les fixtures `fake_captcha` (Turnstile : `required = True` pour l'exiger, jeton valable `"jeton-valide"`), `fake_breach` (mots de passe dans `pwned`) et `fake_google` (identité renvoyée par Google, code valable `"bon-code"`) remplacent les services de connexion. **Aucun test ne doit appeler Yahoo, Anthropic, un vrai serveur de mail, Google, Cloudflare ni Have I Been Pwned.**
- Comptes : `user` est un compte validé, `client` est connecté avec ce compte, `anon_client` est un visiteur et `admin_client` un administrateur. `sign_in(client, db, user)` (`tests/auth_helpers.py`) ouvre une session et pose les cookies et l'en-tête CSRF. Les clients visent `https://testserver` pour que les cookies `Secure` soient renvoyés.

## Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5180, proxy vers l'API de dev
npm test             # Vitest
npx tsc -b           # vérification des types
npm run lint         # oxlint
npm run build
```

### Tests de bout en bout

```bash
cd frontend
npx playwright install chromium   # une seule fois
npm run e2e                       # contre http://localhost:8095 : reconstruisez web et api avant
```

Avant les tests, `e2e/global-setup.ts` crée le compte `e2e@example.com` (commande `app.cli ensure-user` dans le conteneur api) et le connecte une fois : toutes les pages sont testées connectées, sauf `e2e/auth.spec.ts` qui repart en visiteur.

!> Les tests de bout en bout demandent `COOKIE_SECURE=false` dans `.env` (le site local est en HTTP) et des mails envoyés à **Mailpit** : l'inscription y lit le code reçu. Si `.env` vise Brevo, lancez d'abord `docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --wait api worker && docker compose restart web`, sinon chaque essai enverrait un vrai mail à une adresse `@example.com`. `docker compose up -d --wait api worker && docker compose restart web` remet ensuite le SMTP de `.env`.

| Fichier | Vérifie |
|---|---|
| `e2e/smoke.spec.ts` | Les pages principales s'affichent |
| `e2e/layout.spec.ts` | Aucune page n'est coupée entre 1100 et 1440 px, écrans de compte sans défilement horizontal à 390 px |
| `e2e/table.spec.ts` | Alignement des colonnes des tableaux |
| `e2e/seo.spec.ts` | Un seul `h1`, métadonnées, `noindex` sur les pages privées |
| `e2e/auth.spec.ts` | Inscription avec le code lu dans Mailpit, déconnexion, connexion, panneau glissant, vitrine visiteur |
| `e2e/documentation.spec.ts` | Chaque page du guide et de la documentation s'affiche, sans lien cassé |
| `e2e/headers.spec.ts` | En-têtes de sécurité de nginx, et aucune violation de la CSP sur l'application, le guide et la documentation |

## Méthode de travail

- **TDD** : écrire d'abord le test qui échoue, puis le code.
- **Langues** : interface, messages d'erreur, commentaires et docstrings en français. Identifiants en anglais. Messages de commit en anglais, au format *conventional commits* (`feat:`, `fix:`, `docs:`, `chore:`).
- **Git** :
  - une branche par lot ou par sujet ;
  - une fois terminée, la branche est fusionnée dans `master` par une pull request sur https://github.com/gbtclement/PEA ;
  - `.env` n'est jamais versionné.
- **Données personnelles** : toute nouvelle table personnelle porte un `user_id` (UUID), et les routes passent par `get_current_user()` (privée), `get_optional_user()` (publique) ou `require_admin()`.

## Historique du projet

Le projet a été construit par lots. Chaque lot a sa spécification et son plan dans `docs/superpowers/` :

| Lot | Contenu |
|---|---|
| 1. Socle | Docker, base, univers et éligibilité, Yahoo, worker, liste simple |
| 2. Découverte | Indicateurs, score, accueil, Explorer, ETF, fiche d'un titre, favoris |
| 3. Portefeuille | Ordres, frais, positions, graphiques, compteur d'ordres |
| 4. Assistant IA | Chat Claude, outils, streaming, coûts |
| 5. SEO | Métadonnées, schema.org, robots.txt, sitemap, llms.txt |
| 6. CLAUDE.md | Contexte pour Claude Code |
| Prévisions | Signaux, statistiques, prédictions, bulletin de notes |
| Documentation | Guide utilisateur (`/guide/`) et documentation admin (`/documentation/`), en Docsify |
| Fraîcheur des données | Top 10 dès le premier démarrage, passage du soir à 18 h 15, cours toutes les 1 à 5 min |
| Comptes : socle | Inscription avec code par mail, connexion, mot de passe oublié, alerte nouvel appareil, pages privées, admin |

## Dépannage

| Symptôme | Piste |
|---|---|
| `error during connect … dockerDesktopLinuxEngine` | Docker Desktop n'est pas démarré |
| Pages vides après installation | Le worker remplit encore la base : `docker compose logs -f worker` |
| Bandeau « données anciennes » | Yahoo ne répond plus ou limite les requêtes. Le worker réessaiera tout seul |
| L'assistant affiche « pas encore configuré » | `ANTHROPIC_API_KEY` est vide dans `.env` : renseignez-la puis `docker compose up -d api` |
| L'assistant affiche « Réservé aux membres Premium » | Cochez **Premium offert** sur le compte dans l'onglet Admin (ou abonnez-vous en mode test : voir [Abonnement](abonnement.md#tester-en-local)) |
| `npm run gen:api` échoue | L'API de dev (port 8000) n'est pas lancée |
| Connexion impossible en local, sans erreur | `COOKIE_SECURE` n'est pas à `false` : le navigateur refuse les cookies en HTTP |
| Aucun mail reçu | Regardez http://localhost:8025 (Mailpit), puis `docker compose logs worker` et la table `email_log` |
| `403` « Jeton de sécurité manquant » | La requête ne porte pas `X-CSRF-Token` : passez par `apiSend` / `streamSSE` |
