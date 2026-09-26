# PEA Radar

Application personnelle pour repérer des actions éligibles au PEA et suivre son portefeuille.
Outil d'aide à la décision et d'apprentissage — pas un conseil en investissement.

## Lancer l'application

```bash
cp .env.example .env        # la première fois
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

## Fonctionnalités (lot 2)

- **Accueil** : top 10 du score mixte, indices, plus fortes hausses/baisses, carte du marché.
- **Explorer / ETF** : tous les titres, filtres (secteur, pays, place, score, prix, liquidité, favoris) et tris, conservés dans l'URL.
- **Fiche d'un titre** : graphique TradingView (bougies, volume, moyennes 50/200 jours, RSI, MACD), score détaillé, fondamentaux, simulateur « et si j'avais investi », frais estimés, actualités.
- **Réglages** : corrections manuelles de l'éligibilité PEA.

Le score est recalculé toutes les 5 minutes pendant la séance. Il sert à trier et à comprendre, pas à prédire.

## Test de fumée

```bash
cd frontend && npx playwright install chromium   # une fois
npm run e2e                                        # l'application doit tourner sur http://localhost:8095
```

Documentation de conception : `docs/superpowers/specs/`.
