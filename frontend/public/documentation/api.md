# API REST

Toutes les routes sont préfixées par `/api` (`backend/app/main.py`) et passent par nginx sur http://localhost:8095/api/…

?> En mode développement, la documentation interactive générée par FastAPI (Swagger) est sur **http://localhost:8000/docs**, et le schéma OpenAPI sur `/openapi.json`. Le frontend en génère ses types TypeScript avec `npm run gen:api`.

Les erreurs sont renvoyées en JSON, avec un message en français lisible par l'utilisateur. Toutes les entrées sont validées par Pydantic. `detail` est soit un texte, soit, pour les erreurs que le frontend doit reconnaître, un objet :

```json
{"detail": {"code": "invalid_credentials", "message": "Adresse mail ou mot de passe incorrect."}}
```

Le client du frontend en fait une `ApiError(status, message, code)`.

## Accès

- Les routes personnelles (ordres, portefeuille, favoris, réglages, assistant, prévisions) demandent une session : `401` avec le code `not_authenticated` sinon.
- Les requêtes qui modifient quelque chose (`POST`, `PUT`, `PATCH`, `DELETE`) avec une session doivent porter l'en-tête `X-CSRF-Token` : `403` avec le code `csrf` sinon.
- Les routes marquées **admin** renvoient `403` aux autres comptes.

Détails dans [Comptes utilisateurs](comptes.md).

## Comptes

| Méthode | Route | Rôle |
|---|---|---|
| POST | `/auth/register` | Inscription `{first_name, last_name, email, password, accept_terms}`. Envoie le code. Toujours `202`, même si l'adresse existe |
| POST | `/auth/verify-email` | `{email, code}` : valide l'adresse et ouvre une session |
| POST | `/auth/resend-code` | `{email}` : nouveau code, au plus toutes les 60 s |
| POST | `/auth/login` | `{email, password, remember}`. `403 email_not_verified` si l'adresse n'est pas validée |
| POST | `/auth/logout` | Ferme la session courante |
| POST | `/auth/forgot-password` | `{email}` : envoie un lien. Toujours `202` |
| POST | `/auth/reset-password` | `{token, password}` : nouveau mot de passe, toutes les sessions sont fermées |
| POST | `/auth/not-me` | `{token}` : « Ce n'était pas moi » |
| GET | `/me` | Le compte connecté (`id`, `email`, `first_name`, `last_name`, `role`, `is_premium`), ou `401` |

## État

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/health` | `{"status": "ok"}`, utilisé par le healthcheck Docker |
| GET | `/status` | Marché ouvert ou non, dernière réussite ou erreur de chaque tâche, valeur des indices |

## Titres

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/securities?q=&kind=&eligibility=&overridden=&limit=&offset=` | Recherche paginée (nom, ticker, ISIN) |
| GET | `/securities/{id}` | Fiche : cours, score détaillé, fondamentaux, éligibilité, favori |
| GET | `/securities/{id}/history?period=1D\|1W\|1M\|6M\|1Y\|5Y` | Barres OHLCV, MM50/MM200, RSI, MACD. `1D` (barres de 5 min) et `1W` (30 min) sont en intraday, chargés depuis Yahoo et mis en cache |
| PATCH | `/securities/{id}/eligibility` | **Admin.** Correction manuelle : `{"override": "eligible" \| "non_eligible" \| null}` |
| GET | `/securities/{id}/news` | Actualités Yahoo, mises en cache |
| GET | `/securities/{id}/simulate?amount=&period=1W\|1M\|6M\|1Y` | « Si j'avais investi », frais inclus |
| GET | `/screener?kind=stock\|etf` | Toutes les lignes de l'Explorer ou des ETF. Le filtrage et le tri se font côté navigateur |

## Classements et marché

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/rankings/top?limit=10` | Top du score mixte (filtres du top 10 appliqués) |
| GET | `/rankings/movers?limit=5` | Plus fortes hausses et baisses du jour, titres liquides |
| GET | `/market/heatmap` | Données de la carte du marché |

## Favoris et frais

| Méthode | Route | Rôle |
|---|---|---|
| PUT | `/favorites/{security_id}` | Ajouter aux favoris |
| DELETE | `/favorites/{security_id}` | Retirer des favoris |
| GET | `/fees/estimate?amount=` | Frais d'un ordre avec la grille de l'utilisateur |

## Portefeuille

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/orders` | Historique des ordres |
| POST | `/orders` | Nouvel ordre. Frais calculés si absents. **Refus** si survente |
| PUT | `/orders/{id}` | Modifier un ordre (même contrôle) |
| DELETE | `/orders/{id}` | Supprimer un ordre (même contrôle sur les ordres restants) |
| GET | `/orders/counter` | Compteur d'ordres de l'année, rythme et frais de non-respect |
| GET | `/portfolio` | Chiffres clés, positions, répartitions |
| GET | `/portfolio/history` | Valeur jour par jour depuis le premier ordre |

## Réglages

| Méthode | Route | Rôle |
|---|---|---|
| GET / PUT | `/settings` | Ordres minimum par an, frais de non-respect, grille de courtage |
| GET / PUT | `/assistant/settings` | Modèle IA, clé API (en écriture seulement : la lecture indique juste si elle est configurée) |

## Assistant

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/assistant/conversations` | Liste avec le coût de chaque conversation |
| POST | `/assistant/conversations` | Nouvelle conversation (titre sujet optionnel) |
| GET | `/assistant/conversations/{id}` | Messages d'une conversation |
| DELETE | `/assistant/conversations/{id}` | Supprimer une conversation |
| POST | `/assistant/conversations/{id}/messages` | Envoyer un message. **Réponse en flux SSE** |

## Prévisions

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/forecasts` | Prédictions de la dernière séance calculée, pour les 3 horizons |
| GET | `/forecasts/signals` | Statistiques signaux × horizons, référence et frais |
| GET | `/forecasts/track-record` | Test sur l'année écoulée et suivi réel |
| GET | `/securities/{id}/forecast` | Signaux actifs et prédictions d'un titre |

Avant le premier calcul, ces routes renvoient des listes vides avec `as_of: null`.

## Référencement

Relayés par nginx à la racine du site :

| Route API | Adresse publique |
|---|---|
| `/seo/robots.txt` | `/robots.txt` |
| `/seo/sitemap.xml` | `/sitemap.xml` |
| `/seo/llms.txt` | `/llms.txt` |
