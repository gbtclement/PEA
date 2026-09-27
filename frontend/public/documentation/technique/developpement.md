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

- Environ 380 tests, sur une base séparée `pea_radar_test`.
- Les tests marqués `network` (qui appellent le vrai Yahoo) sont exclus par défaut.
- Fixtures : le client de test est dans `tests/conftest.py`, les fabriques de données dans `tests/factories.py`.
- Faux fournisseurs : `tests/fakes.py` (marché) et `tests/fake_llm.py` (Claude). **Aucun test ne doit appeler Yahoo ni Anthropic.**

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

| Fichier | Vérifie |
|---|---|
| `e2e/smoke.spec.ts` | Les pages principales s'affichent |
| `e2e/layout.spec.ts` | Aucune page n'est coupée entre 1100 et 1440 px |
| `e2e/table.spec.ts` | Alignement des colonnes des tableaux |
| `e2e/seo.spec.ts` | Un seul `h1`, métadonnées, `noindex` sur les pages privées |

## Méthode de travail

- **TDD** : écrire d'abord le test qui échoue, puis le code.
- **Langues** : interface, messages d'erreur, commentaires et docstrings en français. Identifiants en anglais. Messages de commit en anglais, au format *conventional commits* (`feat:`, `fix:`, `docs:`, `chore:`).
- **Git** :
  - une branche par lot ou par sujet ;
  - une fois terminée, la branche est fusionnée dans `master` par une pull request sur https://github.com/gbtclement/PEA ;
  - `.env` n'est jamais versionné.
- **Données personnelles** : toute nouvelle table personnelle porte un `user_id`, et les routes passent par `get_current_user()`.

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
| Documentation | Ce site Docsify |

## Dépannage

| Symptôme | Piste |
|---|---|
| `error during connect … dockerDesktopLinuxEngine` | Docker Desktop n'est pas démarré |
| Pages vides après installation | Le worker remplit encore la base : `docker compose logs -f worker` |
| Bandeau « données anciennes » | Yahoo ne répond plus ou limite les requêtes. Le worker réessaiera tout seul |
| L'assistant dit que la clé est invalide après une réinstallation | `APP_SECRET` a changé : ressaisissez la clé dans les Réglages |
| `npm run gen:api` échoue | L'API de dev (port 8000) n'est pas lancée |
