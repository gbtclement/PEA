# PEA Radar

Application personnelle pour repérer des actions éligibles au PEA et suivre son portefeuille.
Outil d'aide à la décision et d'apprentissage — pas un conseil en investissement.

## Lancer l'application

```bash
cp .env.example .env        # la première fois, puis remplacer APP_SECRET par une longue chaîne aléatoire
docker compose up -d --build
```

Puis ouvrir http://localhost:8095. Au premier démarrage, le worker télécharge la liste des
titres puis 5 ans d'historique : comptez une dizaine de minutes avant que tout soit rempli,
et environ une heure pour les données fondamentales.

## Développement

```bash
# Backend (code monté en volume, rechargement automatique, API sur http://localhost:8000)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db api worker
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest

# Frontend (http://localhost:5180, proxy /api vers le port 8000)
cd frontend && npm install && npm run dev
npm test
npm run gen:api   # régénère les types TypeScript depuis l'API
```

## Fonctionnalités

- **Accueil** : top 10 du score mixte, indices, compteur d'ordres de l'année, plus fortes hausses/baisses, carte du marché.
- **Explorer / ETF** : tous les titres, filtres (secteur, pays, place, score, prix, liquidité, favoris) et tris, conservés dans l'URL.
- **Fiche d'un titre** : graphique TradingView (bougies, volume, moyennes 50/200 jours, RSI, MACD), score détaillé, fondamentaux, simulateur « et si j'avais investi », frais estimés, actualités, bouton « + J'ai acheté ».
- **Portefeuille** : saisie manuelle des ordres (frais calculés selon votre grille, modifiables), positions avec PRU frais inclus, plus/moins-values latentes et réalisées, répartition par titre et par secteur, évolution de la valeur, compteur X/12 ordres avec alerte de rythme. Une vente supérieure à la quantité détenue est refusée.
- **Assistant IA** (Claude) : page dédiée avec l'historique des conversations et leur coût estimé, et panneau latéral ouvert par les boutons ✨ (top 10, fiche d'un titre) avec des questions prêtes. Claude consulte les données de l'application (recherche, fiche, historique et indicateurs, top 10, portefeuille, simulation d'achat passé) et l'actualité sur le web ; réponses en direct, mot par mot.
- **Réglages** : clé API Claude (chiffrée en base avec `APP_SECRET`, jamais renvoyée au navigateur ; ou variable `ANTHROPIC_API_KEY`) et modèle IA (Claude Opus 5 par défaut) ; ordres minimum par an, frais en cas de non-respect, grille de courtage de votre caisse régionale ; corrections manuelles de l'éligibilité PEA.

Le score est recalculé toutes les 5 minutes pendant la séance. Il sert à trier et à comprendre, pas à prédire.

## Référencement (SEO)

L'application est prête à être indexée le jour où elle sera mise en ligne :

- chaque page a son titre, sa description, son adresse canonique, ses balises Open Graph/Twitter et ses données schema.org (`WebApplication`, `Corporation`, `InvestmentFund`, `BreadcrumbList`) ;
- `/robots.txt`, `/sitemap.xml` et `/llms.txt` sont générés par l'API ;
- le portefeuille, l'assistant et les réglages sont toujours en `noindex`.

Deux variables dans `.env` :

| Variable | Local (défaut) | En ligne |
|---|---|---|
| `SEO_INDEXING` | `false` : robots.txt interdit tout | `true` : seules les pages publiques (accueil, explorateur, ETF, fiches) sont autorisées |
| `PUBLIC_BASE_URL` | `http://localhost:8095` | l'adresse publique, utilisée dans le sitemap, robots.txt et llms.txt |

À la mise en ligne, prévoir aussi une pré-génération (prerendering) des pages publiques : les moteurs indexent plus sûrement du HTML déjà rempli qu'une application React.

## Tests de bout en bout

```bash
cd frontend && npx playwright install chromium   # une fois
npm run e2e                                        # l'application doit tourner sur http://localhost:8095 (parcours, mise en page de 1100 à 1440 px, SEO)
```

Documentation de conception : `docs/superpowers/specs/`. Contexte pour Claude Code (architecture, commandes, conventions, points d'attention) : `CLAUDE.md`.
