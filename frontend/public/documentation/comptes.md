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
| `admin` | En plus : l'[onglet Admin](#onglet-admin) et la [documentation admin](#documentation-protégée). Toujours considéré comme Premium |

`is_premium` donne accès à l'**assistant IA**. `User.has_premium` est vrai pour un compte Premium ou admin. Pour l'instant, seul l'admin l'active (onglet Admin) ; l'abonnement payant passera plus tard par Stripe.

## Sessions et cookies

Une connexion crée une ligne dans `sessions`. Le navigateur reçoit trois cookies, tous `SameSite=Lax` et `Secure` sauf si `COOKIE_SECURE=false` :

| Cookie | Contenu | Lisible en JavaScript |
|---|---|---|
| `cotalyx_session` | Jeton de session. En base, seule son empreinte SHA-256 est stockée | non |
| `cotalyx_csrf` | Jeton anti-CSRF de la session | **oui**, le frontend le renvoie |
| `cotalyx_device` | Identifiant de l'appareil, conservé 1 an, pour repérer les nouvelles connexions | non |

- **Rester connecté** : session et cookies de 30 jours (`SESSION_DAYS`).
- **Sinon** : cookies effacés à la fermeture du navigateur, et session limitée à 12 h côté serveur (`SESSION_SHORT_HOURS`).
- La déconnexion supprime la session. Un nouveau mot de passe ou « Ce n'était pas moi » supprime **toutes** les sessions du compte.

### CSRF

Toute requête `POST`, `PUT`, `PATCH` ou `DELETE` faite avec une session doit porter l'en-tête `X-CSRF-Token` égal au cookie `cotalyx_csrf`. Sinon l'API répond `403` avec le code `csrf`. Le client HTTP du frontend (`apiSend`, `streamSSE`) l'ajoute tout seul.

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
| `/verifier-email`, `/mot-de-passe-oublie`, `/reinitialiser`, `/ce-n-etait-pas-moi`, `/accepter-cgu`, `/desinscription` | Tout le monde, `noindex` |
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
| `password_check` | Mots de passe actuels faux dans les Réglages (changer de mot de passe, d'adresse, supprimer le compte) | 10 en 15 min | `429 too_many_requests`, même avec le bon mot de passe |

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
| `password_changed` | Mot de passe changé (ou ajouté) depuis les Réglages |
| `email_changed` | Nouvelle adresse validée depuis les Réglages |
| `session_revoked` | Appareil déconnecté (`details.all_others` : tous les autres) |
| `terms_accepted` | Nouvelle version des CGU acceptée (`details.version`) |
| `data_export` | Export des données demandé |
| `unsubscribed` | Désinscription par le lien d'un mail (`details.kind` : le type de mail, ou `all`) |
| `account_deleted` | Compte supprimé sans admin (`details.reason` : `self` par son titulaire, `inactivity` par le worker) |
| `admin_user_updated` | Compte modifié par un admin (`actor_id`, `details.fields`) |
| `admin_user_deleted` | Compte supprimé par un admin (`user_id` passe à vide, `actor_id` reste) |
| `admin_settings_updated` | Modèle ou limite de l'assistant changé (`details` : les nouvelles valeurs) |
| `billing_consent` | Cases CGV et renonciation au droit de rétractation cochées avant un paiement (`details.cgv_version`, `details.interval`) |
| `duplicate_subscription` | Deuxième abonnement payé alors qu'un premier donne déjà accès (deux onglets) : il est résilié tout de suite, à rembourser depuis Stripe (`details.subscription_id`) |
| `subscription_started` | Abonnement Premium activé (`details.interval`) |
| `subscription_ended` | Accès Premium par abonnement terminé (`details.status`) |

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
      pose le cookie signé cotalyx_oauth (state, nonce, vérificateur PKCE, page de retour ; 10 min)
  → Google (choix du compte)
  → GET /api/auth/google/callback?state=…&code=…
      vérifie le state (usage unique), échange le code, vérifie le jeton d'identité (signature, émetteur, audience, nonce)
      ├─ adresse non vérifiée par Google → /connexion?erreur=google_email
      ├─ compte connu (google_sub ou même adresse) → session ouverte, retour à la page demandée
      └─ inconnu → cookie signé cotalyx_google_pending (30 min) → /finaliser-inscription
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

## Profil et appareils

Les Réglages (`/reglages`) regroupent ce qui concerne le compte connecté (routes `/api/me…`, `backend/app/services/auth/profile.py`) :

- **Profil** : prénom et nom.
- **Mot de passe** : l'actuel est demandé. Le changement ferme toutes les **autres** sessions et envoie un mail `security_alert`. Un compte créé avec Google, sans mot de passe, voit « Ajouter un mot de passe » et n'a rien à confirmer.
- **Adresse mail** : un code à 6 chiffres part vers la nouvelle adresse (même quota que les autres codes). La réponse est la même si l'adresse est déjà prise, pour ne pas révéler les comptes existants. Une fois le code validé, les **autres** sessions sont fermées et l'ancienne adresse reçoit une alerte.
- **Appareils connectés** : chaque session ouverte, avec l'appareil déduit du navigateur, l'IP et la dernière activité. On peut en déconnecter une, ou toutes les autres.

## Onglet Admin

`/admin` n'apparaît dans la barre latérale que pour un admin ; un autre compte qui ouvre l'adresse voit la page introuvable. Côté API, toutes les routes `/api/admin/*` passent par `require_admin()`.

- **Utilisateurs** : 50 comptes par page, recherche (mail, prénom, nom, sans tenir compte des accents), tri sur chaque colonne. La colonne Premium dit d'où il vient : « Abonné (mensuel) », « Abonné (annuel) », « Offert » ou « Admin » ; l'interrupteur **Premium offert** le donne sans paiement.
- **Modifier** : prénom, nom, adresse, rôle, Premium offert (l'abonnement Stripe éventuel est affiché, en lecture seule). Une adresse changée par l'admin est considérée comme validée ; l'ancienne et la nouvelle adresse sont prévenues par mail. Tout autre changement, sauf la bascule Premium offert, prévient le titulaire (`security_alert`). Un changement de **rôle** ou d'**adresse** ferme toutes ses sessions.
- **Supprimer** : il faut retaper l'adresse du compte. Toutes ses données partent avec lui (`ON DELETE CASCADE`) et un mail `account_deleted` lui est envoyé.
- **Garde-fous** : un admin ne peut ni retirer son propre rôle (`self_demotion`), ni supprimer son propre compte ici (`self_delete`), et il reste toujours au moins un admin (`last_admin`).
- **État de la configuration** : pour chaque réglage de `.env` (Claude, SMTP, Google, Turnstile, `APP_SECRET`, `ADMIN_EMAIL`, Stripe), « Renseigné » ou « Manquant ». Pour Stripe, le mode (test ou réel, déduit du début de la clé) et l'heure du dernier webhook reçu. **Aucune valeur n'est jamais renvoyée.** Un bouton envoie un mail de test à l'admin.
- **Corrections d'éligibilité PEA** (voir [Éligibilité](eligibilite.md)) et lien vers cette documentation.

## Assistant : Premium et limite de coût

Premium (assistant et prévisions) vient du rôle admin, de la case **Premium offert** ou d'un abonnement payant : voir [Abonnement (Stripe)](abonnement.md).

- La clé Claude ne se règle que dans `.env` (`ANTHROPIC_API_KEY`) : aucun secret n'est stocké en base ni affiché dans l'interface.
- Le **modèle** et la **limite mensuelle par utilisateur** (5 $ par défaut) sont communs à tous et se règlent dans l'onglet Admin. Ils sont stockés dans `app_settings` (une seule ligne, lue par `get_app_settings()`).
- Le coût de chaque réponse est ajouté par `add_cost()` dans `ai_usage` (utilisateur × mois). Il n'est jamais recalculé depuis les conversations : supprimer une conversation ne rend pas de budget.
- Le mois est celui de **Paris** : la limite repart le 1er à minuit. Les admins sont comptés comme les autres.
- La limite est vérifiée **avant** chaque question. La dernière réponse du mois peut donc la dépasser de son propre coût.
- Le coût est enregistré **avant** le message : une conversation supprimée pendant la réponse est quand même comptée.
- `GET /api/assistant/status` dit à l'interface si l'assistant est disponible, et sinon pourquoi : « Réservé aux membres Premium », « Assistant pas encore configuré » ou « Limite du mois atteinte ».

## Documentation protégée

`/documentation/` (cette documentation) est servie par nginx, hors de l'application React. Avant chaque fichier, nginx demande à l'API si la session est admin (`auth_request` vers `GET /api/auth/admin-check`, qui répond `204` ou `401`). Un visiteur ou un membre est renvoyé vers `/connexion?suite=%2Fdocumentation%2F`, et la connexion le ramène ici par une navigation complète. Les réponses portent `Cache-Control: no-store`.

Le guide utilisateur (`/guide/`) et les fichiers Docsify communs (`/docsify/`) restent publics.

## CGU versionnées

`TERMS_VERSION` (`backend/app/core/terms.py`) est la date du texte des CGU en vigueur. Chaque compte garde la version acceptée (`users.terms_version`).

- `get_current_user()`, utilisé par toutes les pages privées, répond `403 terms_outdated` si la version du compte n'est pas la bonne.
- `get_account_user()` sert aux routes du compte lui-même (`/me`, appareils, export, suppression, `POST /me/accept-terms`) : elles restent ouvertes, pour pouvoir accepter, exporter ou partir.
- `GET /api/me` renvoie `terms_outdated`. L'interface envoie alors toute page vers `/accepter-cgu?suite=<page>` : une case à cocher, puis retour à la page demandée. Les pages légales restent lisibles, et l'écran propose, sous « Vous ne souhaitez pas les accepter ? », l'export et la suppression du compte.
- Une page restée ouverte au changement reçoit `403 terms_outdated` : le client relit alors le compte (`createQueryClient()`, `frontend/src/lib/queryClient.ts`), ce qui déclenche la redirection.

**Quand les CGU changent** : mettre à jour le texte (`frontend/src/features/legal/content.tsx`, avec `LEGAL_UPDATED`), puis la date de `TERMS_VERSION`. Chacun devra accepter à sa prochaine visite.

## Export des données

Carte « Mes données » des Réglages (`POST /api/me/export`, `backend/app/services/privacy/export.py`) :

- La demande crée une ligne `data_exports` en attente. Le worker la prépare dans les **15 s** (tâche `exports`) : un fichier JSON avec le profil, les réglages, les ordres, les favoris, les conversations, l'usage de l'assistant et les appareils. Mots de passe, jetons et identifiants internes n'y sont jamais.
- Le titulaire reçoit le mail C7 et télécharge le fichier depuis les Réglages (`GET /api/me/export/{id}`, sa session seulement). Le fichier est gardé **7 jours**.
- Un export à la fois (`409 export_pending`, garanti par un index unique sur les exports en attente), un par jour au plus (`429 export_limit`).
- Statuts : `pending`, `ready` ou `failed`. Un export qui plante passe à `failed` sans bloquer les autres, et un export bloqué plus d'une heure passe à `failed` (tâche `cleanup`). Après un échec, le titulaire peut en redemander un tout de suite.

## Suppression du compte

Trois chemins, une seule fonction : `erase_account()` (`backend/app/services/privacy/erasure.py`), appelée par le titulaire (`DELETE /api/me`), par un admin, ou par le worker pour inactivité.

- Toutes les données du compte partent avec lui (`ON DELETE CASCADE`). Le mail C6 confirme la suppression.
- Le journal de sécurité garde ses lignes, sans lien vers le compte. Dans l'historique des mails, chaque adresse est remplacée par son **empreinte** (`supprimé:…`) : on peut reconnaître une même adresse, pas la lire. Le contenu des mails (montants, titres, prénom) est effacé. Les mails encore en attente sont annulés. Si le mail C6 reste en attente plus de 7 jours (pas de SMTP), son adresse est remplacée par l'empreinte.
- Le titulaire retape son adresse et donne son mot de passe. Un compte Google sans mot de passe doit s'être reconnecté avec Google il y a **moins de 5 minutes** (`403 reauth_required` sinon).
- Un abonnement Stripe vivant est mis en file (`stripe_cancellations`) et résilié chez Stripe par le worker dans la minute, sans remboursement.
- Le dernier admin ne peut pas supprimer son compte (`last_admin`). Le compte des admins verrouille leurs lignes : deux admins qui partent en même temps ne passent pas tous les deux.

## Durées de conservation

Appliquées chaque nuit à **3 h 30** par la tâche `cleanup` du worker (`backend/app/services/privacy/retention.py`) :

| Donnée | Durée |
|---|---|
| Compte et données saisies | Jusqu'à la suppression, ou **3 ans** sans connexion : mail C8, puis suppression 30 jours après si le compte n'est pas revenu. Jamais un admin, ni un abonné Premium payant |
| Compte dont l'adresse n'a pas été validée | 7 jours |
| Sessions, codes et liens | Jusqu'à leur expiration |
| Export des données | 7 jours |
| Historique des mails | 90 jours |
| Photos quotidiennes des scores (`score_snapshots`) | 14 jours |
| Titres déjà signalés par N1 (`move_notices`) | 7 jours |
| Journal de sécurité | 12 mois |
| Compteurs anti-abus | 1 jour |
| Abonnement et accords de vente (`subscriptions`, `billing_consents`) | Jusqu'à la suppression du compte |
| Événements Stripe déjà traités (`stripe_events`) | 30 jours |

Toute connexion, ou l'usage d'une session « rester connecté », compte comme activité (`last_login_at`, `last_seen_at`).

Le détail des traitements est dans le [registre des traitements](registre.md).

## Notifications

Six mails que le membre choisit dans la carte « Notifications par mail » des Réglages (`/reglages#notifications`, `GET/PUT /api/me/notifications`). Code : `backend/app/services/notifications/`, tâches : `backend/app/jobs/notifications.py`.

| | Type interne | Par défaut | Quand | Tâche du worker |
|---|---|---|---|---|
| N1 | `price_move` | Activé | Toutes les 15 min en séance : un favori ou une position bouge d'au moins le seuil (5 % par défaut, de 1 à 50 %). Une fois par titre et par jour | `price_moves` |
| N2 | `price_alert` | Activé | Après chaque mise à jour des cours : une alerte de prix franchit son seuil | `quotes_t*` |
| N3 | `daily_recap` | Désactivé | 18 h 45 les jours de bourse | `daily_recap` |
| N4 | `weekly_recap` | Désactivé | Samedi 9 h | `weekly_recap` |
| N5 | `order_reminder` | Activé | 1er octobre, novembre et décembre à 9 h, s'il manque des ordres pour éviter les frais de la caisse | `order_reminders` |
| N6 | `score_change` | Désactivé | Après le calcul du soir : un favori entre ou sort du top 10, ou son score bouge d'au moins 10 points | `evening` |

- **Un seul point d'entrée** : `notify()` (`services/notifications/send.py`). Il vérifie la préférence, ajoute le lien de désinscription et met le mail en file avec `enqueue()`. Une notification ne passe jamais par `enqueue()` directement.
- **Désinscription** : chaque mail porte le lien « Ne plus recevoir ce mail » vers `/desinscription`, et l'en-tête `List-Unsubscribe` (désinscription en un clic depuis la messagerie, `POST /api/unsubscribe`). Le jeton n'est pas stocké : c'est `<user_id>.<HMAC-SHA256(APP_SECRET, …)>`. **Sans `APP_SECRET`, aucune notification ne part** (message dans les journaux du worker). Les mails du compte (codes, sécurité) ne sont pas concernés.
- **Alertes de prix** : créées depuis la fiche d'un titre (« Créer une alerte »), **50 actives** au plus (`alert_limit`), refusées si le cours a déjà franchi le seuil (`already_reached`). Une alerte déclenchée se désactive ; le membre la réarme dans les Réglages. Si N2 est désactivé, les alertes restent en place mais aucun mail ne part.
- **Photos des scores** : `score_snapshots` garde le score de chaque titre chaque soir pour N6, **14 jours**. `move_notices` retient les titres déjà signalés par N1, **7 jours**.

## Étape suivante

Toutes les étapes des comptes sont faites, y compris l'abonnement Premium payant : voir [Abonnement (Stripe)](abonnement.md).
