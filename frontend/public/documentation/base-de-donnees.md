# Base de données

PostgreSQL 16, conteneur `db`, données dans le volume Docker `pgdata`. Modèles SQLAlchemy 2 (API synchrone) dans `backend/app/models/`. Migrations Alembic dans `backend/alembic/versions/`, appliquées automatiquement au démarrage de l'API (`backend/docker/entrypoint-api.sh`).

## Tables

| Table | Contenu | Personnelle (`user_id`) |
|---|---|---|
| `users` | Comptes : identifiant **UUID**, adresse mail, prénom, nom, empreinte du mot de passe (Argon2, vide pour un compte Google seul), identifiant Google (`google_sub`), blocage (`locked_until`), rôle `user`/`admin`, `is_premium`, date de validation de l'adresse, version des CGU acceptée | — |
| `sessions` | Sessions ouvertes : empreinte du jeton, jeton CSRF, « rester connecté », expiration, dernière activité, appareil | **oui** |
| `known_devices` | Appareils déjà utilisés par chaque compte, pour le mail « nouvelle connexion » | **oui** |
| `email_codes` | Codes à 6 chiffres et liens (nouveau mot de passe, « Ce n'était pas moi ») : empreinte, usage, expiration, essais | **oui** |
| `email_log` | File d'envoi et historique des mails : type, destinataire, contenu, statut `pending`/`sent`/`failed`, essais, erreur. Le contenu des mails à code ou à lien est effacé une fois envoyé | **oui** (peut être vide) |
| `security_events` | Journal de sécurité : type d'événement, IP, détails (JSON), date. Gardé 12 mois | **oui** (peut être vide) |
| `rate_limit_hits` | Tentatives comptées par les limites anti-abus : compteur, empreinte de l'adresse ou de l'IP, date. Gardé 1 jour | non |
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

## Migration des comptes (UUID)

La migration `a7c3e9f1b2d4_user_accounts` transforme les identifiants entiers des utilisateurs en **UUID** dans `users` et dans toutes les tables personnelles, et crée les tables des comptes. L'ancien utilisateur par défaut devient le compte « Moi » (`moi@pea-radar.invalid`), repris ensuite par `ADMIN_EMAIL` (voir [Comptes utilisateurs](comptes.md)).

!> Cette migration est **à sens unique** : il n'y a pas de retour arrière. **Sauvegardez la base avant** la première reconstruction qui l'applique (voir plus bas).

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

?> Les données personnelles tiennent en peu de lignes : ordres, favoris, réglages, conversations. Tout le reste (cours, scores, prévisions) se reconstruit automatiquement depuis Yahoo. Pensez à sauvegarder au moins les tables `users` et `orders`.
