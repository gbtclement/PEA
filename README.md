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

Documentation de conception : `docs/superpowers/specs/`.
