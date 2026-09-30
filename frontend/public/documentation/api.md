# API REST

Toutes les routes sont préfixées par `/api` (`backend/app/main.py`) et passent par nginx sur http://localhost:8095/api/…

?> En mode développement, la documentation interactive générée par FastAPI (Swagger) est sur **http://localhost:8000/docs**, et le schéma OpenAPI sur `/openapi.json`. Le frontend en génère ses types TypeScript avec `npm run gen:api`.

Les erreurs sont renvoyées en JSON, avec un message en français lisible par l'utilisateur. Toutes les entrées sont validées par Pydantic. `detail` est soit un texte, soit, pour les erreurs que le frontend doit reconnaître, un objet :

```json
{"detail": {"code": "invalid_credentials", "message": "Adresse mail ou mot de passe incorrect."}}
```

Le client du frontend en fait une `ApiError(status, message, code)`.

## Accès

- Les routes personnelles (ordres, portefeuille, favoris, réglages, assistant, prévisions) demandent une session : `401` avec le code `not_authenticated` sinon. Elles répondent `403 terms_outdated` tant que le compte n'a pas accepté la version en vigueur des CGU ; les routes `/me…` restent ouvertes (voir [Comptes](comptes.md#cgu-versionnées)).
- Les requêtes qui modifient quelque chose (`POST`, `PUT`, `PATCH`, `DELETE`) avec une session doivent porter l'en-tête `X-CSRF-Token` : `403` avec le code `csrf` sinon.
- Les routes marquées **admin** renvoient `403` aux autres comptes.

Détails dans [Comptes utilisateurs](comptes.md).

## Comptes

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/auth/config` | Ce que le serveur active : `{google, turnstile_site_key}` (bouton Google, widget Turnstile) |
| POST | `/auth/register` | Inscription `{first_name, last_name, email, password, accept_terms, captcha}`. Envoie le code. Toujours `202`, même si l'adresse existe |
| POST | `/auth/verify-email` | `{email, code}` : valide l'adresse et ouvre une session |
| POST | `/auth/resend-code` | `{email}` : nouveau code, au plus toutes les 60 s |
| POST | `/auth/login` | `{email, password, remember, captcha}`. `403 email_not_verified` si l'adresse n'est pas validée. `captcha` n'est exigé qu'après 3 échecs |
| POST | `/auth/logout` | Ferme la session courante |
| POST | `/auth/forgot-password` | `{email, captcha}` : envoie un lien. Toujours `202` |
| POST | `/auth/reset-password` | `{token, password}` : nouveau mot de passe, toutes les sessions sont fermées |
| POST | `/auth/not-me` | `{token}` : « Ce n'était pas moi » |
| GET | `/auth/google/start` | `?suite=<page>&remember=1\|0` : redirige vers Google. `404 google_disabled` si Google n'est pas configuré |
| GET | `/auth/google/callback` | Retour de Google : ouvre la session et redirige vers `suite`, ou vers `/finaliser-inscription` pour un nouveau compte, ou vers `/connexion?erreur=google\|google_email` |
| GET | `/auth/google/pending` | Nouveau compte Google en attente : `{email, first_name, last_name}`, ou `404 google_expired` |
| POST | `/auth/google/complete` | `{first_name, last_name, accept_terms}` : crée le compte Google et ouvre la session. `400 google_expired` après 30 min |
| GET | `/auth/admin-check` | `204` pour un admin connecté, `401` sinon. Appelée par nginx (`auth_request`) avant de servir `/documentation/` |
| GET | `/me` | Le compte connecté (`id`, `email`, `first_name`, `last_name`, `role`, `is_premium`, `has_premium`, `has_password`, `has_google`, `terms_outdated`), ou `401` |
| PATCH | `/me` | `{first_name, last_name}` : modifier son profil |
| POST | `/me/password` | `{current_password, new_password}` : change le mot de passe et ferme les **autres** sessions. `current_password` n'est pas demandé à un compte Google sans mot de passe (« Ajouter un mot de passe ») |
| POST | `/me/email` | `{new_email, password}` : envoie un code à la nouvelle adresse. Toujours `202`, même si l'adresse est déjà prise |
| POST | `/me/email/verify` | `{code}` : valide la nouvelle adresse et ferme les **autres** sessions ; l'ancienne adresse reçoit une alerte |
| GET | `/me/sessions` | Appareils connectés : `[{id, device, ip, created_at, last_seen_at, current}]` |
| DELETE | `/me/sessions/{id}` | Déconnecter un appareil |
| DELETE | `/me/sessions` | Déconnecter tous les autres appareils |
| POST | `/me/accept-terms` | `{accept_terms: true}` : accepter la version en vigueur des CGU. Renvoie le compte |
| POST | `/me/export` | Demander l'export de ses données (`202`, `{id, status, created_at, expires_at}`). Préparé par le worker, mail quand il est prêt |
| GET | `/me/export` | Le dernier export (`pending`, `ready` ou `failed`), ou `null` |
| GET | `/me/export/{id}` | Télécharger le fichier JSON, 7 jours. `404` après, ou pour un autre compte |
| GET | `/me/notifications` | Préférences : `{price_move, price_alert, daily_recap, weekly_recap, order_reminder, score_change, move_threshold_pct}` (valeurs par défaut si jamais enregistrées) |
| PUT | `/me/notifications` | Les mêmes champs : enregistre les préférences. `move_threshold_pct` de 1 à 50 |
| GET | `/me/price-alerts` | Alertes de prix : `[{id, security_id, symbol, name, currency, direction, price, current_price, active, triggered_at, created_at}]` |
| POST | `/me/price-alerts` | `{security_id, direction: "above"|"below", price}` : créer une alerte (`201`). Prix dans la devise du titre |
| PATCH | `/me/price-alerts/{id}` | `{active: true}` : réarmer une alerte déclenchée (mêmes contrôles qu'à la création) |
| DELETE | `/me/price-alerts/{id}` | Supprimer une alerte (`204`) |
| GET | `/unsubscribe?jeton=&type=` | **Sans connexion.** Vérifie le lien d'un mail : `{kind, label}`, ou `404 bad_link` |
| POST | `/unsubscribe?jeton=&type=` | **Sans connexion.** Désactive ce type de mail, ou toutes les notifications sans `type`. Aussi appelée par la messagerie (`List-Unsubscribe` en un clic) |
| DELETE | `/me` | `{confirm_email, password}` : supprimer son compte et toutes ses données. `204` et cookies effacés. `password` est ignoré pour un compte Google sans mot de passe, qui doit s'être reconnecté depuis moins de 5 min |

Codes d'erreur des routes de compte, en plus de `invalid_credentials`, `email_not_verified` et des erreurs de code ou de lien :

| Code | Statut | Quand |
|---|---|---|
| `captcha_required` | 400 | Jeton Turnstile absent ou refusé (inscription, mot de passe oublié, connexion après 3 échecs) |
| `weak_password` | 400 | Mot de passe trop court (moins de 12 caractères) ou trop long |
| `pwned_password` | 400 | Mot de passe connu dans les fuites (Have I Been Pwned) |
| `account_locked` | 429 | 10 mots de passe faux en 15 min pour cette adresse |
| `too_many_requests` | 429 | Trop de tentatives depuis cette IP, ou 10 mots de passe actuels faux en 15 min dans les Réglages (voir [Comptes](comptes.md#limites-anti-abus)) |
| `bad_origin` | 403 | En-tête `Origin` étranger |
| `google_disabled` | 404 | Google n'est pas configuré |
| `google_expired` | 400 / 404 | Inscription Google en attente depuis plus de 30 min |
| `wrong_password` | 400 | Mot de passe actuel faux (`/me/password`, `/me/email`, `DELETE /me`) |
| `terms_outdated` | 403 | Nouvelle version des CGU à accepter (`POST /me/accept-terms`) |
| `confirm_mismatch` | 400 | `DELETE /me` : l'adresse retapée n'est pas celle du compte |
| `reauth_required` | 403 | `DELETE /me`, compte Google sans mot de passe : se reconnecter avec Google, puis confirmer dans les 5 min |
| `export_pending` | 409 | Un export est déjà en préparation |
| `export_limit` | 429 | Un export par jour au plus |
| `alert_limit` | 400 | 50 alertes de prix actives au plus |
| `already_reached` | 400 | Le cours a déjà franchi le seuil de l'alerte |
| `bad_link` | 404 | Lien de désinscription faux ou abîmé |
| `email_taken` | 409 | Adresse prise par un autre compte : entre la demande et la validation du code, ou choisie par l'admin |
| `self_demotion` | 400 | Un admin retire son propre rôle d'administrateur |
| `last_admin` | 400 | Le dernier admin perdrait son rôle |
| `self_delete` | 400 | Un admin supprime son propre compte depuis l'onglet Admin |
| `confirm_mismatch` | 400 | Adresse retapée différente de celle du compte à supprimer |

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

## Assistant

Toutes les routes, sauf `/assistant/status`, sont réservées aux membres **Premium** (les admins le sont toujours) : `403 premium_required` sinon.

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/assistant/status` | `{available, reason, spent_usd, limit_usd, model}`. Quand `available` est faux, `reason` vaut `premium`, `not_configured` ou `limit_reached` |
| GET | `/assistant/conversations` | Liste avec le coût de chaque conversation |
| POST | `/assistant/conversations` | Nouvelle conversation (titre sujet optionnel) |
| GET | `/assistant/conversations/{id}` | Messages d'une conversation |
| DELETE | `/assistant/conversations/{id}` | Supprimer une conversation |
| POST | `/assistant/conversations/{id}/messages` | Envoyer un message. **Réponse en flux SSE**. `409 ai_not_configured` sans `ANTHROPIC_API_KEY`, `429 ai_limit_reached` quand la limite du mois est atteinte |

## Admin

Toutes ces routes sont **admin** (`require_admin()`).

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/admin/users?q=&sort=&order=&page=` | Inscrits, 50 par page. `q` cherche dans le mail, le prénom et le nom, sans tenir compte des accents. `sort` : `email`, `first_name`, `last_name`, `role`, `is_premium`, `verified`, `created_at` (par défaut), `last_login_at` |
| PATCH | `/admin/users/{id}` | `{first_name, last_name, email, role, is_premium}`, tous facultatifs. Un changement de rôle ou d'adresse ferme les sessions du compte. Refus `self_demotion`, `last_admin`, `email_taken` |
| DELETE | `/admin/users/{id}` | `{confirm_email}` : supprime le compte et ses données. Refus `self_delete`, `confirm_mismatch` |
| GET / PUT | `/admin/settings` | `{ai_model, ai_monthly_cost_limit_usd}` ; la lecture ajoute la liste `models` |
| GET | `/admin/config-status` | Ce qui est renseigné dans `.env` : `{claude, smtp, google, turnstile, app_secret, admin_email}`, des booléens, **jamais les valeurs** |
| POST | `/admin/test-email` | Met un mail de test en file d'attente pour l'admin connecté |

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
