# Base de données

PostgreSQL 16, conteneur `db`, données dans le volume Docker `pgdata`. Modèles SQLAlchemy 2 (API synchrone) dans `backend/app/models/`. Migrations Alembic dans `backend/alembic/versions/`, appliquées automatiquement au démarrage de l'API (`backend/docker/entrypoint-api.sh`).

## Tables

| Table | Contenu | Personnelle (`user_id`) |
|---|---|---|
| `users` | Utilisateurs. Un utilisateur par défaut est créé au démarrage | — |
| `securities` | Univers : ISIN, ticker Yahoo, nom, type `stock`/`etf`/`index`, place, pays, secteur, éligibilité automatique et correction, actif | non |
| `quotes` | Dernier cours connu de chaque titre : prix, variation du jour, volume, horodatage | non |
| `daily_prices` | Historique journalier OHLCV sur 5 ans | non |
| `fundamentals` | PER, BPA, croissances, dette/capitaux propres, marge, dividende, capitalisation | non |
| `scores` | Dernier score : total, technique, fondamental, détail JSON, liquidité, montant moyen échangé, données incomplètes, entrée dans le top | non |
| `favorites` | Titres favoris | **oui** |
| `orders` | Ordres : date, sens, quantité, prix unitaire, frais, note | **oui** |
| `user_settings` | Clé API chiffrée, modèle IA, ordres minimum, frais de non-respect, grille de courtage (JSON) | **oui** |
| `conversations` | Conversations de l'assistant (titre, titre-sujet optionnel) | **oui** |
| `messages` | Messages : contenu, outils utilisés, tokens, coût estimé | **oui** (via la conversation) |
| `forecast_runs` | Calculs complets des prévisions : statistiques, test, coupure, frais (JSON) | non |
| `forecasts` | Prédictions (titre, jour, horizon) puis leur résultat réel | non |
| `data_status` | Dernière réussite, dernière erreur et nombre d'éléments par tâche du worker | non |

## Migrations

```bash
# Créer une migration après avoir modifié un modèle
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api alembic revision --autogenerate -m "description"

# Appliquer les migrations
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api alembic upgrade head
```

Relisez toujours le fichier généré avant de le committer : l'autogénération d'Alembic ne détecte pas tout, par exemple les renommages.

## Se connecter à la base

```bash
docker compose exec db psql -U pea -d pea_radar
```

```sql
SELECT job, last_success_at, last_error FROM data_status;       -- état du worker
SELECT count(*) FROM securities WHERE kind = 'stock';           -- taille de l'univers
```

## Sauvegarder et restaurer

```bash
docker compose exec -T db pg_dump -U pea pea_radar > sauvegarde.sql
docker compose exec -T db psql -U pea -d pea_radar < sauvegarde.sql
```

?> Les données personnelles tiennent en peu de lignes : ordres, favoris, réglages, conversations. Tout le reste (cours, scores, prévisions) se reconstruit automatiquement depuis Yahoo. Pensez à sauvegarder au moins la table `orders`.
