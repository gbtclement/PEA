# Comptes utilisateurs

Chaque membre a son propre portefeuille, ses favoris, ses conversations et ses réglages. Les données de marché (titres, cours, scores, prévisions) sont communes. La conception complète est dans `docs/superpowers/specs/2026-09-28-comptes-utilisateurs-design.md`.

Le code est réparti ainsi :

| Emplacement | Contenu |
|---|---|
| `backend/app/api/routes/auth.py`, `me.py` | Routes `/api/auth/*` et `/api/me` |
| `backend/app/core/current_user.py` | Dépendances `get_optional_user`, `get_current_user`, `require_admin` et contrôle CSRF |
| `backend/app/services/auth/` | Comptes, codes et liens, sessions, appareils connus, reprise par l'admin |
| `backend/app/services/mail/` | Rendu des mails, file d'envoi (`enqueue`), envoi SMTP |
| `backend/app/jobs/mail.py` | Tâche du worker qui vide la file |
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

## Étape suivante

Le lot `comptes-securite` ajoutera la connexion avec Google, Cloudflare Turnstile sur les formulaires, le blocage après plusieurs mots de passe faux et des limites de débit par adresse IP.
