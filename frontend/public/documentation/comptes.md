# Comptes utilisateurs

Chaque membre a son propre portefeuille, ses favoris, ses conversations et ses réglages. Les données de marché (titres, cours, scores, prévisions) sont communes. La conception complète est dans `docs/superpowers/specs/2026-09-28-comptes-utilisateurs-design.md`.

Le code est réparti ainsi :

| Emplacement | Contenu |
|---|---|
| `backend/app/api/routes/auth.py`, `google.py`, `me.py` | Routes `/api/auth/*`, `/api/auth/google/*` et `/api/me` |
| `backend/app/api/origin.py` | Contrôle de l'en-tête `Origin` sur les routes publiques de compte |
| `backend/app/core/current_user.py` | Dépendances `get_optional_user`, `get_current_user`, `require_admin` et contrôle CSRF |
| `backend/app/services/auth/` | Comptes, codes et liens, sessions, appareils connus, reprise par l'admin, Google (`google.py`), Turnstile (`captcha.py`), fuites de mots de passe (`breach.py`) |
| `backend/app/services/ratelimit.py`, `security_log.py` | Limites anti-abus et journal de sécurité |
| `backend/app/services/mail/` | Rendu des mails, file d'envoi (`enqueue`), envoi SMTP |
| `backend/app/jobs/mail.py`, `cleanup.py` | Tâches du worker : vider la file de mails, purger journal et compteurs |
| `frontend/src/features/auth/` | Écrans de compte, `useMe`, `RequireAuth` |

## Rôles

| Rôle | Droits |
|---|---|
| Visiteur | Pages publiques seulement |
| `user` | Ses propres données |
| `admin` | En plus : corrections d'éligibilité (`PATCH /securities/{id}/eligibility`). Toujours `is_premium` |

`is_premium` existe déjà en base mais ne débloque encore rien.

## Sessions et cookies

Une connexion crée une ligne dans `sessions`. Le navigateur reçoit trois cookies, tous `SameSite=Lax` et `Secure` sauf si `COOKIE_SECURE=false` :

| Cookie | Contenu | Lisible en JavaScript |
|---|---|---|
| `pea_session` | Jeton de session. En base, seule son empreinte SHA-256 est stockée | non |
| `pea_csrf` | Jeton anti-CSRF de la session | **oui**, le frontend le renvoie |
| `pea_device` | Identifiant de l'appareil, conservé 1 an, pour repérer les nouvelles connexions | non |

- **Rester connecté** : session et cookies de 30 jours (`SESSION_DAYS`).
- **Sinon** : cookies effacés à la fermeture du navigateur, et session limitée à 12 h côté serveur (`SESSION_SHORT_HOURS`).
- La déconnexion supprime la session. Un nouveau mot de passe ou « Ce n'était pas moi » supprime **toutes** les sessions du compte.

### CSRF

Toute requête `POST`, `PUT`, `PATCH` ou `DELETE` faite avec une session doit porter l'en-tête `X-CSRF-Token` égal au cookie `pea_csrf`. Sinon l'API répond `403` avec le code `csrf`. Le client HTTP du frontend (`apiSend`, `streamSSE`) l'ajoute tout seul.

## Codes et liens envoyés par mail

Codes et liens sont stockés dans `email_codes`, **uniquement sous forme d'empreinte**. Chacun ne sert qu'une fois.

| Usage | Forme | Validité |
|---|---|---|
| Validation de l'adresse | Code à 6 chiffres, 5 essais au maximum | 15 min. Nouveau code possible au bout de 60 s |
| Nouveau mot de passe | Lien `/reinitialiser?jeton=…` | 30 min (24 h pour le lien envoyé à l'admin au démarrage) |
| « Ce n'était pas moi » | Lien `/ce-n-etait-pas-moi?jeton=…` dans le mail de nouvel appareil | 7 jours |

Les routes qui reçoivent une adresse mail (`register`, `resend-code`, `forgot-password`) répondent toujours la même chose, qu'un compte existe ou non.

## Envoi des mails

L'API n'envoie **jamais** de mail elle-même :

1. `enqueue()` ajoute une ligne `pending` dans `email_log`, dans la même transaction que l'action. Elle ne fait pas de commit.
2. Toutes les 5 s, le worker envoie les mails en attente par SMTP.
3. En cas d'échec, il réessaie après 1 min, 5 min puis 30 min. Ensuite le mail passe en `failed` et l'erreur est écrite dans les journaux du worker.
4. Dès qu'un mail portant un code ou un lien (`verify_code`, `reset_password`, `new_device`) est `sent` ou `failed`, son objet et son contenu sont effacés : la copie en base ne permet plus de se connecter.

```sql
SELECT id, kind, recipient, status, attempts, error, created_at FROM email_log ORDER BY id DESC LIMIT 20;
```

En local, les mails arrivent dans **Mailpit** : http://localhost:8025. En ligne, ce sont les identifiants SMTP de Brevo (voir [Installation](installation.md)).

## Administrateur et commandes

Au démarrage, l'API lance `python -m app.cli bootstrap-admin` :

- le compte `ADMIN_EMAIL` devient `admin` ;
- s'il n'existe pas encore, il **reprend le compte « Moi »** d'avant les comptes, avec tout son portefeuille ;
- s'il n'a pas de mot de passe, un lien valable 24 h lui est envoyé pour en choisir un, une seule fois.

La ligne correspondante apparaît dans `docker compose logs api`.

```bash
# Rejouer la reprise par l'admin
docker compose exec -T api python -m app.cli bootstrap-admin

# Créer ou réparer un compte déjà validé (tests, dépannage), avec --admin en option
docker compose exec -T api python -m app.cli ensure-user --email prenom@exemple.fr --password "un-long-mot-de-passe" --first-name Prénom --last-name Nom
```

## Pages publiques et privées

| Pages | Accès |
|---|---|
| `/`, `/explorer`, `/etf`, `/titres/:id`, `/cgu`, `/confidentialite`, `/mentions-legales` | Tout le monde, indexables |
| `/connexion`, `/inscription` | Tout le monde, indexables, hors de la mise en page de l'application |
| `/verifier-email`, `/mot-de-passe-oublie`, `/reinitialiser`, `/ce-n-etait-pas-moi` | Tout le monde, `noindex` |
| `/previsions`, `/portefeuille`, `/assistant`, `/reglages` | Membres. Un visiteur est renvoyé vers `/connexion?suite=<page>` |

Côté API, les routes personnelles (ordres, portefeuille, favoris, réglages, assistant, prévisions) renvoient `401` sans session.

## Limites anti-abus

Chaque tentative est comptée dans `rate_limit_hits` sur une fenêtre glissante (`LIMITS` dans `backend/app/services/ratelimit.py`). Adresses et IP n'y sont stockées que **sous forme d'empreinte**. Chaque nuit à 3 h 30, le worker purge les lignes de plus d'un jour.

| Compteur (`bucket`) | Ce qui est compté | Limite | Au-delà |
|---|---|---|---|
| `login_account` | Mots de passe faux pour une adresse | 10 en 15 min | `429 account_locked` pendant 15 min, même avec le bon mot de passe. Même réponse que le compte existe ou non |
| `login_ip` | Mots de passe faux depuis une IP | 30 en 15 min | `429 too_many_requests` |
| `signup_ip` | Inscriptions depuis une IP | 5 par heure | `429 too_many_requests` |
| `mail_ip` | Demandes de code ou de lien depuis une IP | 20 par heure | `429 too_many_requests` |
| `mail_account` | Codes et liens envoyés à une adresse | 5 par heure | Réponse inchangée, mais plus rien n'est envoyé |
| `oauth_state` | Retours de Google avec le même `state` | 1 en 10 min | Retour refusé (`/connexion?erreur=google`) |

Après **3** mots de passe faux (par adresse ou par IP, `CAPTCHA_AFTER`), la connexion exige Turnstile. Une connexion réussie remet à zéro le compteur de l'adresse.

L'IP retenue est la **dernière** de `X-Forwarded-For`, celle qu'ajoute notre nginx. Derrière un proxy HTTPS placé devant nginx, toutes les requêtes sembleraient venir de ce proxy : configurer `set_real_ip_from` dans nginx avant la mise en ligne (voir [SEO et mise en ligne](seo.md#à-prévoir-avant-une-mise-en-ligne)).

Débloquer un compte à la main :

```sql
UPDATE users SET locked_until = NULL, failed_logins = 0 WHERE email = 'prenom@exemple.fr';
DELETE FROM rate_limit_hits WHERE bucket = 'login_account';  -- tous les comptes : les clés sont des empreintes
```

## Journal de sécurité

Les événements de compte sont écrits dans `security_events` par `log_event()` (`backend/app/services/security_log.py`). Ils sont gardés **12 mois**, puis purgés par le worker.

| `kind` | Quand |
|---|---|
| `signup` | Inscription par mot de passe |
| `email_verified` | Code de validation accepté |
| `login_ok` | Connexion (`details.method` : `password` ou `google`) |
| `login_failed` | Mot de passe faux (`user_id` vide si l'adresse n'a pas de compte) |
| `locked` | 10ᵉ échec : compte bloqué 15 min |
| `logout` | Déconnexion |
| `password_reset` | Nouveau mot de passe choisi par lien |
| `not_me` | « Ce n'était pas moi » |
| `google_linked` | Compte Google associé à un compte existant |
| `google_signup` | Compte créé avec Google |

```sql
SELECT e.created_at, e.kind, u.email, e.ip, e.details
FROM security_events e LEFT JOIN users u ON u.id = e.user_id
ORDER BY e.id DESC LIMIT 50;
```

## Connexion avec Google

Le bouton n'apparaît que si `GOOGLE_CLIENT_ID` et `GOOGLE_CLIENT_SECRET` sont remplis (voir `GET /api/auth/config`). Le flux suit OpenID Connect, avec PKCE :

```
Bouton « Continuer avec Google »
  → GET /api/auth/google/start?suite=…&remember=1|0
      pose le cookie signé pea_oauth (state, nonce, vérificateur PKCE, page de retour ; 10 min)
  → Google (choix du compte)
  → GET /api/auth/google/callback?state=…&code=…
      vérifie le state (usage unique), échange le code, vérifie le jeton d'identité (signature, émetteur, audience, nonce)
      ├─ adresse non vérifiée par Google → /connexion?erreur=google_email
      ├─ compte connu (google_sub ou même adresse) → session ouverte, retour à la page demandée
      └─ inconnu → cookie signé pea_google_pending (30 min) → /finaliser-inscription
                   → POST /api/auth/google/complete (prénom, nom, CGU) → compte créé, session ouverte
```

- Les deux cookies sont `HttpOnly`, limités au chemin `/api/auth/google` et signés avec `APP_SECRET`.
- **Adresse d'un compte existant** : le compte Google lui est associé (`google_sub`). Un mail `security_alert` prévient le propriétaire et l'événement `google_linked` est journalisé.
- **Compte existant jamais validé** : son mot de passe est **effacé** avant l'association. Google vient de prouver qui possède l'adresse, alors que rien ne prouve que ce mot de passe a été choisi par cette personne.
- Toute erreur côté Google renvoie vers `/connexion?erreur=google`, qui affiche un message.

## Cloudflare Turnstile

Turnstile remplace le captcha classique : le plus souvent, la case se coche toute seule.

- Il est demandé à **l'inscription**, pour le **mot de passe oublié** et à la **connexion après 3 échecs**. Sans jeton valable, l'API répond `400 captcha_required`.
- `TURNSTILE_SECRET_KEY` vide : captcha **désactivé**, tout passe (local, tests). `TURNSTILE_SITE_KEY` vide : pas de widget.
- Si Cloudflare ne répond pas en 5 s, la vérification est **ignorée**, avec un avertissement dans `docker compose logs api`. Mieux vaut laisser passer que bloquer tout le monde, et les limites ci-dessus restent actives.

## Mots de passe apparus dans des fuites

À l'inscription et au changement de mot de passe, l'API interroge **Have I Been Pwned** (`backend/app/services/auth/breach.py`) :

- seuls les **5 premiers caractères** de l'empreinte SHA-1 partent (k-anonymat), avec l'en-tête `Add-Padding`, et la comparaison se fait chez nous ;
- délai maximal de **2 s** : si le service ne répond pas, le mot de passe est accepté ;
- `HIBP_ENABLED=false` coupe la vérification ;
- en cas de refus, l'API répond `400 pwned_password`.

## Contrôle de l'origine

Les routes publiques de compte (`register`, `verify-email`, `resend-code`, `login`, `logout`, `forgot-password`, `reset-password`, `not-me`, `google/complete`) refusent un en-tête `Origin` qui n'est ni `PUBLIC_BASE_URL` ni l'une des `DEV_ORIGINS` : `403 bad_origin`. Une requête sans `Origin` (outil en ligne de commande) est acceptée.

## Étape suivante

Le lot `comptes-admin` ajoutera l'onglet Admin (utilisateurs, rôles, Premium), la clé Claude uniquement dans `.env` avec une limite de coût, l'état de la configuration, la protection de `/documentation/` et la réorganisation des réglages (profil, appareils).
