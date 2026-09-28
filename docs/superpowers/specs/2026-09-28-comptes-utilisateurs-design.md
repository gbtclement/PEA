# Comptes utilisateurs, admin et mails — conception

**Date :** 2026-09-28

**Demande de l'utilisateur :**
- une page de **connexion / inscription** obligatoire avant d'accéder à l'application privée, avec un bloc qui **glisse** entre inscription et connexion (inspiration : Dribbble « Fixem Sign Up Page »), aux couleurs de l'app ;
- inscription avec **prénom, nom, mail** et mot de passe, compte **validé par un code reçu par mail** ;
- connexion et inscription **avec Google** ;
- identifiants **UUID** ; la sécurité est laissée au choix de Claude ;
- réglages séparés : **utilisateur** et **admin** ; deux rôles, `user` et `admin` ;
- onglet **Admin** : liste des inscrits (recherche et tri par mail, nom, prénom), colonne et bascule **Premium**, modification et suppression (pas de création) ;
- **toutes les clés et secrets dans `.env`** (Claude, SMTP, Google, captcha), plus aucun secret en base ni saisi dans l'interface ;
- des **mails** : liés au compte et notifications, activables/désactivables par l'utilisateur ;
- mise en ligne **publique** : CGU, confidentialité (RGPD), et plus tard CGV avec un **abonnement** (au moins pour l'assistant IA).

**Décisions prises pendant la conception :**
- mot de passe classique (pas de connexion par code seul) ;
- sessions côté serveur dans un cookie `HttpOnly` (pas de JWT, pas de service d'authentification externe) ;
- captcha **Cloudflare Turnstile** (gratuit sans limite, pas de pistage publicitaire) plutôt que reCAPTCHA ;
- envoi des mails en **SMTP** configuré dans `.env` (Brevo probablement), **Mailpit** en développement ;
- **vitrine publique** (accueil, fiches, explorateur, classement restent lisibles sans compte, SEO du lot 5 conservé) et **app privée** ;
- **Premium** donne accès à l'assistant IA ; le paiement viendra plus tard.

## 1. Données

### 1.1 Table `users` (transformée)

L'identifiant devient un **UUID** (`uuid4`), y compris comme clé primaire. La migration convertit les `user_id` de `orders`, `favorites`, `conversations` et `user_settings`.

| Colonne | Type | Remarque |
|---|---|---|
| `id` | UUID | clé primaire |
| `email` | texte | unique, stocké en minuscules, index |
| `first_name`, `last_name` | texte (100) | |
| `password_hash` | texte, nullable | Argon2id ; vide pour un compte uniquement Google |
| `google_sub` | texte, nullable, unique | identifiant stable du compte Google |
| `role` | `user` \| `admin` | défaut `user` |
| `is_premium` | booléen | défaut `false` |
| `email_verified_at` | date/heure, nullable | |
| `terms_accepted_at`, `terms_version` | date/heure, texte | version des CGU acceptée |
| `failed_logins`, `locked_until` | entier, date/heure | blocage temporaire |
| `inactivity_warned_at` | date/heure, nullable | mail C8 envoyé |
| `created_at`, `last_login_at`, `last_seen_at` | date/heure | |

La colonne `name` disparaît (remplacée par prénom et nom).

### 1.2 Nouvelles tables

| Table | Contenu |
|---|---|
| `sessions` | `id` UUID, `user_id`, **empreinte SHA-256 du jeton** (jamais le jeton), `csrf_token`, appareil (navigateur, système, lu dans le User-Agent), IP tronquée (/24 en IPv4, /48 en IPv6), `persistent` (« rester connecté »), `created_at`, `last_seen_at`, `expires_at` |
| `known_devices` | `user_id`, empreinte d'un cookie d'appareil longue durée, `first_seen_at` : sert à détecter un nouvel appareil (C5) |
| `email_codes` | `user_id`, but (`verify_email`, `change_email`, `reset_password`), empreinte du code ou du jeton, nouvelle adresse (pour `change_email`), `attempts`, `expires_at`, `used_at` |
| `notification_prefs` | `user_id` (clé primaire), un booléen par notification N1 à N6, `move_threshold_pct` (N1, défaut 5), `unsubscribe_token` |
| `price_alerts` | `id` UUID, `user_id`, `security_id`, `direction` (`above` \| `below`), `price`, `active`, `triggered_at`, `created_at` |
| `email_log` | `id`, `user_id` (nullable après suppression), `kind` (C1…C8, N1…N6, `test`), destinataire, sujet, corps HTML et texte, `status` (`pending` \| `sent` \| `failed`), `attempts`, `next_attempt_at`, `sent_at`, `dedupe_key` (unique, nullable), `created_at` |
| `security_events` | `id`, `user_id` (nullable), `actor_id` (admin qui agit, nullable), `kind`, IP tronquée, détails JSON, `created_at` |
| `app_settings` | une seule ligne : `ai_model` (modèle par défaut de l'assistant), `ai_monthly_cost_limit_usd` (défaut 5) |
| `data_exports` | `id` UUID, `user_id`, `status`, chemin du fichier, `expires_at` (7 jours) |

### 1.3 Retraits

- `user_settings.anthropic_key_enc` et `user_settings.ai_model` sont supprimés. La clé Claude est lue **uniquement** dans `ANTHROPIC_API_KEY` ; le modèle vient de `app_settings`.
- `services/secrets.py` (chiffrement Fernet de la clé) et la carte « Assistant IA » des réglages utilisateur sont supprimés. `APP_SECRET` reste utilisé pour signer les jetons de désinscription et d'appareil.

### 1.4 Reprise de l'existant

Au démarrage (et dans la migration pour la partie structure) :
- l'utilisateur existant « Moi » devient le compte `ADMIN_EMAIL` (`.env`), rôle `admin`, Premium, mail considéré comme validé, CGU à accepter à la première connexion ; toutes ses données sont conservées ;
- s'il n'a pas de mot de passe, un lien C3 lui est envoyé au premier démarrage ; il peut aussi se connecter avec Google si c'est la même adresse ;
- si `ADMIN_EMAIL` désigne un compte déjà existant, il reçoit le rôle `admin`. L'admin n'est jamais créé ni promu autrement que par cette variable ou par un autre admin.
- `ensure_default_user` disparaît.

### 1.5 Abonnement (plus tard)

`is_premium` suffit. Quand le paiement arrivera, une table `subscriptions` le mettra à jour ; elle n'est pas créée maintenant.

## 2. Authentification et sécurité

### 2.1 Sessions

- À la connexion, l'API crée un jeton aléatoire de 256 bits, enregistre son empreinte dans `sessions` et l'envoie dans le cookie **`pea_session`** : `HttpOnly`, `Secure` (sauf en local, réglé par `COOKIE_SECURE`), `SameSite=Lax`, `Path=/`.
- Durée : **30 jours glissants** si « rester connecté », sinon cookie de session du navigateur et 12 h glissantes côté serveur. `last_seen_at` est mis à jour au plus une fois par minute.
- **CSRF** : un second cookie `pea_csrf` lisible par le JavaScript ; toute requête qui modifie (`POST`, `PUT`, `PATCH`, `DELETE`) doit renvoyer sa valeur dans l'en-tête `X-CSRF-Token`, comparée à celle de la session. Les routes publiques de connexion et d'inscription vérifient en plus l'en-tête `Origin`.
- `get_current_user()` (`core/current_user.py`) lit le cookie, charge la session et l'utilisateur, et renvoie **401** si absent ou expiré. Nouvelles dépendances :
  - `get_optional_user()` pour les pages publiques qui s'adaptent si l'on est connecté ;
  - `require_verified_user()` (compte validé et CGU à jour, sinon 403 avec un code d'erreur que le frontend traduit en redirection) ;
  - `require_admin()` et `require_premium()`.
- Une session est **révoquée** à la déconnexion, au changement de mot de passe ou de mail (toutes les autres sessions), à la réinitialisation du mot de passe (toutes), à la suppression du compte, au changement de rôle par un admin et sur « Ce n'était pas moi » (C5).
- Au changement de privilège (connexion, validation), l'identifiant de session est régénéré.

### 2.2 Mots de passe

- **Argon2id** (`argon2-cffi`, paramètres par défaut de la bibliothèque, re-hachage automatique s'ils changent).
- 12 caractères minimum, 128 maximum, aucune règle de composition imposée.
- Vérification **Have I Been Pwned** (k-anonymat : seuls les 5 premiers caractères du SHA-1 sont envoyés). Si le service ne répond pas en 2 s, la vérification est ignorée.
- Jauge de solidité côté navigateur (indicative) ; la règle qui fait foi est côté serveur.

### 2.3 Codes et liens

- **Code de validation** : 6 chiffres, valable **15 minutes**, **5 essais** au maximum, puis il faut en demander un nouveau. Renvoi possible après 60 s. Un nouveau code annule le précédent.
- **Lien de réinitialisation** : jeton aléatoire de 256 bits, valable **30 minutes**, à usage unique.
- Seules les empreintes sont stockées ; les comparaisons se font en temps constant.

### 2.4 Anti-abus

Limites en base PostgreSQL (pas de Redis), comptées sur une fenêtre glissante :

| Action | Limite |
|---|---|
| Connexion | 10 échecs par compte en 15 min → blocage de 15 min ; 30 échecs par IP en 15 min → 429 |
| Captcha à la connexion | demandé après 3 échecs pour ce compte ou cette IP |
| Inscription | 5 par IP et par heure, Turnstile toujours demandé |
| Envoi de code / mot de passe oublié | 5 par compte et par heure, 20 par IP et par heure, Turnstile demandé pour le mot de passe oublié |

- **Turnstile** : vérification côté serveur avec `TURNSTILE_SECRET_KEY` ; si `TURNSTILE_SECRET_KEY` est vide (local, tests), la vérification est désactivée.
- **Pas de fuite d'information** : inscription avec un mail déjà pris et mot de passe oublié sur un mail inconnu affichent le même message que le cas normal. Dans le cas d'une inscription avec un mail déjà pris, le propriétaire reçoit un mail l'informant de la tentative, avec un lien de réinitialisation.
- L'adresse IP réelle est lue dans `X-Forwarded-For` posé par nginx (seul proxy de confiance).

### 2.5 Connexion Google

- OpenID Connect, flux « authorization code » avec **PKCE** et `state`/`nonce`, fait **côté serveur** (bibliothèque `authlib`) : `GET /api/auth/google/start` redirige vers Google, `GET /api/auth/google/callback` échange le code, vérifie le jeton d'identité et crée la session. Le navigateur ne voit jamais les jetons Google.
- Portées : `openid email profile`. Données gardées : `sub`, mail, prénom, nom. La photo n'est pas stockée.
- Cas :
  - `google_sub` connu → connexion ;
  - sinon mail connu **et** `email_verified` vrai côté Google → le compte Google est **rattaché**, mail C4 « Un compte Google a été associé » ;
  - sinon → création du compte (mail considéré comme validé), puis écran « Finaliser l'inscription » (acceptation des CGU, prénom et nom modifiables) ;
  - `email_verified` faux → refus avec un message clair.
- Un compte Google peut ajouter un mot de passe depuis son profil.
- `.env` : `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`. S'ils sont vides, le bouton Google est masqué.

### 2.6 En-têtes nginx

`Content-Security-Policy` (sources propres, plus `challenges.cloudflare.com` pour Turnstile), `Strict-Transport-Security` (seulement derrière HTTPS, activé par variable), `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` restrictive, `X-Frame-Options: DENY`.

### 2.7 Journal de sécurité

`security_events` enregistre : inscription, validation, connexion réussie ou échouée, blocage, déconnexion, changement de mot de passe ou de mail, rattachement Google, « Ce n'était pas moi », export, suppression, et toute action d'un admin. Aucun mot de passe, code ou jeton n'y figure. Conservation 12 mois.

## 3. Parcours

### 3.1 Pages publiques et privées

- **Publiques** (vitrine, SEO du lot 5 conservé) : accueil, fiches des titres, explorateur, classement, ETF, guide `/guide/`, pages légales, connexion et inscription. Un bandeau discret invite les visiteurs à créer un compte gratuit.
- **Privées** : portefeuille, favoris, prévisions, assistant, réglages, admin. Sans session, redirection vers `/connexion?suite=<page demandée>` ; après connexion, retour à cette page (seulement si c'est un chemin interne).
- Les éléments personnels sur les pages publiques (étoile de favori, par exemple) invitent à se connecter.
- L'API applique la même séparation : les routes publiques restent lisibles par les robots, les routes personnelles exigent `require_verified_user()`.

### 3.2 Inscription

1. `/inscription` : prénom, nom, mail, mot de passe (jauge, bouton afficher), case obligatoire « J'accepte les CGU et la politique de confidentialité », Turnstile.
2. Compte créé non validé, code C1 envoyé, écran `/verifier-email` : 6 cases, « Renvoyer le code » (après 60 s), « Modifier l'adresse ».
3. Code correct → mail validé, session ouverte, mail C2, arrivée sur l'accueil.

Un compte non validé qui se connecte arrive sur `/verifier-email`. Les comptes jamais validés sont supprimés au bout de 7 jours.

### 3.3 Connexion

`/connexion` : mail, mot de passe, « Rester connecté », « Mot de passe oublié ? ». Même message d'erreur que le mail existe ou non. Turnstile et blocage selon 2.4. Si le navigateur n'a pas de cookie d'appareil connu pour ce compte, mail **C5** (information, non bloquant).

### 3.4 Mot de passe oublié

`/mot-de-passe-oublie` (mail + Turnstile) → mail C3 → `/reinitialiser?jeton=…` (nouveau mot de passe) → toutes les sessions révoquées, mail C4, connexion.

### 3.5 CGU mises à jour

La version courante est une constante (`TERMS_VERSION`). Si `terms_version` de l'utilisateur est différente, `require_verified_user()` renvoie 403 `terms_outdated` et le frontend affiche `/accepter-cgu`.

### 3.6 Déconnexion

Bouton dans la barre latérale (menu du compte, avec prénom et nom). Révoque la session courante.

## 4. Réglages et Admin

### 4.1 Réglages utilisateur (`/reglages`)

- **Profil** : prénom, nom ; mot de passe (demande l'actuel ; « Ajouter un mot de passe » pour un compte Google) ; mail (code envoyé à la nouvelle adresse, C4 à l'ancienne) ; appareils connectés avec « Déconnecter » et « Déconnecter tous les autres » ; « Exporter mes données » ; « Supprimer mon compte » (mot de passe demandé, ou reconnexion Google de moins de 5 minutes pour un compte sans mot de passe).
- **Notifications** : un interrupteur par mail N1 à N6 et le seuil de N1.
- **Frais et obligations** : carte actuelle, inchangée, propre à chaque utilisateur.

### 4.2 Onglet Admin (`/admin`)

Visible dans la barre latérale pour le rôle `admin` uniquement ; toutes les routes `/api/admin/*` passent par `require_admin()`. Page en `noindex`.

- **Utilisateurs** :
  - colonnes : prénom, nom, mail, rôle, **Premium** (interrupteur dans le tableau), compte validé, méthodes de connexion (mot de passe, Google), inscription, dernière connexion ;
  - recherche (mail, nom, prénom, insensible à la casse et aux accents), tri sur chaque colonne, pagination côté serveur (50 par page) ;
  - **Modifier** : prénom, nom, mail, rôle, Premium. Changer le mail d'un utilisateur le marque comme validé (l'admin en prend la responsabilité) et envoie C4 aux deux adresses ;
  - **Supprimer** : confirmation en retapant le mail, suppression du compte et de toutes ses données, mail C6 ;
  - garde-fous : un admin ne peut ni se supprimer, ni retirer son propre rôle admin, ni retirer le dernier admin ;
  - pas de création de compte.
- **Assistant IA** : modèle par défaut (liste du catalogue existant) et **limite de coût mensuelle par utilisateur** en dollars (défaut 5). Quand la limite est atteinte, l'assistant l'indique et refuse de nouvelles questions jusqu'au mois suivant. Le coût est déjà calculé par message (`messages.cost_usd`).
- **État de la configuration** : pour Claude, SMTP, Google et Turnstile, ✓ ou ✗ selon que les variables de `.env` sont renseignées, **sans jamais afficher de valeur**. Bouton « Envoyer un mail de test » à sa propre adresse.
- **Documentation admin** : nginx protège `/documentation/` avec `auth_request` vers `GET /api/auth/admin-check` (200 si la session est admin, 401 sinon → redirection vers `/connexion`).

### 4.3 Premium

`require_premium()` protège les routes de l'assistant. Les autres voient sur `/assistant` une carte « Réservé aux membres Premium » expliquant que l'abonnement arrivera bientôt. Les admins sont toujours considérés comme Premium.

## 5. Mails

### 5.1 Liste

**Liés au compte** (toujours envoyés, sans désinscription) :

| Code | Mail | Déclenchement |
|---|---|---|
| C1 | Code de validation | inscription, renvoi, changement de mail (nouvelle adresse) |
| C2 | Bienvenue (premiers pas, lien vers le guide) | compte validé ou créé avec Google |
| C3 | Réinitialisation du mot de passe | demande, ou premier démarrage de l'admin sans mot de passe |
| C4 | Alerte sécurité | mot de passe changé ou réinitialisé, mail changé (ancienne adresse), compte Google associé, tentative d'inscription avec son adresse, modification par un admin |
| C5 | Connexion depuis un nouvel appareil, avec « Ce n'était pas moi » | connexion depuis un appareil inconnu |
| C6 | Compte supprimé | suppression par l'utilisateur ou par un admin |
| C7 | Export de vos données prêt | export terminé |
| C8 | Suppression pour inactivité dans 30 jours | 3 ans sans connexion |

**Notifications** (au choix, désinscription en un clic) :

| Code | Mail | Défaut | Déclenchement |
|---|---|---|---|
| N1 | Forte variation d'un favori ou d'une position (± seuil, 5 % par défaut) | activé | en séance, toutes les 15 min ; un mail regroupant les titres concernés ; au plus une fois par titre et par jour |
| N2 | Seuil de prix personnel (« au-dessus / en dessous de … € ») | activé | après chaque mise à jour des cours ; l'alerte se désactive une fois déclenchée et peut être réarmée |
| N3 | Récap du soir (valeur du portefeuille, variation du jour, plus fortes hausses et baisses des favoris) | désactivé | 18 h 45 les jours de bourse |
| N4 | Récap de la semaine (performance, entrées et sorties du top 10, prévisions vérifiées) | désactivé | samedi 9 h |
| N5 | Rappel du compteur d'ordres (« il te manque N ordres, sinon environ X € de frais ») | activé | 1er octobre, 1er novembre, 1er décembre à 9 h, s'il manque des ordres selon ses réglages de frais |
| N6 | Changement de score d'un favori (entrée ou sortie du top 10, ± 10 points) | désactivé | après le passage du soir |

**Exclus volontairement** : prévisions par mail (prudence AMF), dividendes et résultats à venir (données Yahoo incomplètes), relance d'inactivité commerciale, mails d'abonnement (avec les CGV).

Les alertes de prix N2 se créent depuis la fiche d'un titre (bouton « Créer une alerte ») et se gèrent dans les réglages de notifications. Au plus 50 alertes actives par utilisateur.

### 5.2 Fonctionnement

- `backend/app/services/mail/` :
  - `templates/` : modèles **Jinja2**, une version HTML (styles en ligne, aux couleurs de l'app) et une version texte par mail, en français, sur un gabarit commun (logo, pied de page, lien « Gérer mes notifications », et pour les notifications l'avertissement « outil d'aide à la décision, pas un conseil en investissement ») ;
  - `render.py` : fonctions pures qui produisent sujet, HTML et texte à partir des données ;
  - `outbox.py` : `enqueue(kind, user, context, dedupe_key=None)` ajoute une ligne `pending` dans `email_log` ; la clé `dedupe_key` (par exemple `N1:<user>:<titre>:<date>`) empêche les doublons ;
  - `smtp.py` : envoi via `smtplib` derrière une interface `Mailer`, avec un `FakeMailer` pour les tests.
- **Le worker** envoie la file toutes les **5 secondes** ; en cas d'échec, nouvel essai à 1 min, 5 min puis 30 min, puis `failed`. L'API n'envoie jamais directement.
- En-têtes des notifications : `List-Unsubscribe` (URL et `mailto` facultatif) et `List-Unsubscribe-Post: List-Unsubscribe=One-Click`. Le lien `GET /desinscription?jeton=…` affiche une page de confirmation ; `POST` désactive la notification (ou toutes).
- `.env` : `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_TLS` (`starttls` \| `ssl` \| `none`), `MAIL_FROM`, `PUBLIC_BASE_URL` (déjà présente, pour les liens).
- **Développement** : service **Mailpit** dans `docker-compose.dev.yml` (SMTP sur 1025, interface sur http://localhost:8025).

## 6. RGPD et pages légales

### 6.1 Pages

Rendues par le routeur React, publiques et indexables, liées dans le pied de page et depuis l'écran de connexion :
- `/mentions-legales` : éditeur, hébergeur, contact ;
- `/cgu` : objet, accès réservé aux **18 ans et plus**, compte et sécurité, avertissement **AMF** (pas un conseil en investissement, données différées, sans garantie), assistant IA, suspension et suppression, responsabilité, droit applicable ;
- `/confidentialite` : responsable du traitement, données, finalités et bases légales, durées, sous-traitants, transferts hors UE, droits et contact, cookies.

Claude écrit des **brouillons complets** ; les éléments à fournir (identité ou SIRET de l'éditeur, hébergeur, adresse de contact) sont marqués `[À COMPLÉTER]` et une relecture par un professionnel est conseillée avant la mise en ligne. `/cgv` n'existe pas avant l'abonnement.

### 6.2 Cookies

Uniquement des cookies strictement nécessaires (`pea_session`, `pea_csrf`, cookie d'appareil) et Turnstile, mesure de sécurité : **pas de bandeau de consentement**. À revoir si des statistiques de visite ou de la publicité sont ajoutées.

### 6.3 Sous-traitants déclarés

Hébergeur, Brevo (mails), Google (connexion Google, pour ceux qui l'utilisent), Cloudflare (Turnstile), **Anthropic** (messages de l'assistant, traités aux États-Unis ; rappel sur la page de l'assistant).

### 6.4 Droits

- **Accès et portabilité** : `POST /api/me/export` ; le worker produit un JSON (profil, réglages, préférences, ordres, favoris, alertes, conversations et messages), puis mail C7 avec un lien valable 7 jours qui exige d'être connecté. Un export à la fois, au plus un par jour.
- **Rectification** : profil.
- **Effacement** : suppression immédiate du compte et de ses données (cascade). `security_events` et `email_log` gardent la ligne avec `user_id` à vide et le mail remplacé par une empreinte.
- **Opposition** : préférences et désinscription en un clic.

### 6.5 Durées de conservation

Tâche du worker chaque nuit à 3 h :
- comptes jamais validés : supprimés au bout de 7 jours ;
- sessions expirées, codes expirés, exports expirés : supprimés ;
- `email_log` : 90 jours ; `security_events` : 12 mois ;
- comptes sans connexion depuis 3 ans : mail C8, puis suppression 30 jours après si toujours aucune connexion. Les admins sont exclus.

### 6.6 Registre des traitements

Nouvelle page de la documentation admin qui reprend 6.1 à 6.5 sous forme de registre.

## 7. Écran de connexion et d'inscription

- Carte centrée d'environ 960 × 600 px, coins arrondis, ombre douce, sur un fond clair légèrement dégradé ; couleurs de l'app (`primary` indigo, Inter).
- Deux moitiés : les formulaires, et un **panneau indigo** (logo PEA Radar, phrase d'accroche, courbe de cours stylisée, bouton de changement de mode).
  - Mode inscription : formulaire à gauche, panneau à droite « Déjà un compte ? » + **Se connecter**.
  - Au clic, le panneau **glisse vers la gauche** (environ 600 ms, `transform`), le formulaire d'inscription s'efface et celui de connexion apparaît à droite ; le panneau dit « Pas encore de compte ? » + **S'inscrire**.
  - L'URL suit le mode (`/inscription`, `/connexion`) ; le bouton retour du navigateur fonctionne.
- Dans chaque formulaire : « Continuer avec Google » en haut, séparateur « ou », puis les champs.
- Accessibilité : navigation au clavier, focus sur le premier champ après le glissement, pas d'animation si `prefers-reduced-motion`.
- En dessous de 768 px : le panneau devient un bandeau en haut, sans glissement (écran d'entrée d'un site public, donc utilisable sur mobile, contrairement au reste de l'app).
- `/verifier-email`, `/mot-de-passe-oublie`, `/reinitialiser`, `/finaliser-inscription` (Google) et `/accepter-cgu` reprennent la même carte.
- Pages en `noindex` sauf `/connexion` et `/inscription`.
- Le design sera ajusté avec l'utilisateur sur l'écran réel.

## 8. API (résumé)

| Route | Rôle |
|---|---|
| `POST /api/auth/register`, `/verify-email`, `/resend-code` | inscription et validation |
| `POST /api/auth/login`, `/logout` | connexion, déconnexion |
| `POST /api/auth/forgot-password`, `/reset-password` | mot de passe oublié |
| `GET /api/auth/google/start`, `/google/callback`, `POST /api/auth/google/complete` | Google |
| `POST /api/auth/not-me` | « Ce n'était pas moi » (jeton du mail C5) |
| `GET /api/auth/config` | clé publique Turnstile, Google activé ou non |
| `GET /api/auth/admin-check` | pour `auth_request` de nginx |
| `GET/PATCH /api/me`, `POST /api/me/password`, `/me/email`, `/me/email/verify`, `/me/accept-terms` | profil |
| `GET /api/me/sessions`, `DELETE /api/me/sessions/{id}`, `DELETE /api/me/sessions` | appareils |
| `POST /api/me/export`, `GET /api/me/export/{id}`, `DELETE /api/me` | RGPD |
| `GET/PUT /api/me/notifications`, `GET/POST/PATCH/DELETE /api/me/price-alerts` | notifications |
| `GET/POST /api/unsubscribe` | désinscription en un clic |
| `GET /api/admin/users`, `PATCH/DELETE /api/admin/users/{id}` | admin utilisateurs |
| `GET/PUT /api/admin/settings`, `GET /api/admin/config-status`, `POST /api/admin/test-email` | admin réglages |

Les routes personnelles existantes (ordres, favoris, portefeuille, réglages de frais, assistant) gardent leurs chemins et passent par `require_verified_user()` ; l'assistant, en plus, par `require_premium()`.

## 9. `.env`

Ajouts à `.env.example` (avec commentaires en français) : `ADMIN_EMAIL`, `COOKIE_SECURE`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_TLS`, `MAIL_FROM`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`, `HSTS_ENABLED`. `ANTHROPIC_API_KEY` devient la seule source de la clé Claude.

## 10. Tests

- **Backend (pytest)** :
  - inscription, validation (code faux, expiré, trop d'essais), connexion, blocage, déconnexion, mot de passe oublié, changement de mail ;
  - Google avec un faux fournisseur OIDC (création, rattachement, `email_verified` faux) ;
  - CSRF, cookies, expiration et révocation des sessions ;
  - **isolation** : un utilisateur ne voit jamais les ordres, favoris, alertes ou conversations d'un autre, et les UUID d'un autre renvoient 404 ;
  - rôles (403 sur `/api/admin/*`), Premium, garde-fous de l'admin, limite de coût de l'assistant ;
  - file d'envoi avec `FakeMailer` (nouvel essai, déduplication), rendu de chaque mail, déclenchement de chaque notification N1 à N6, durées de conservation, export ;
  - migration : l'utilisateur « Moi » et ses données deviennent le compte admin.
  - Aucun test n'appelle Google, Cloudflare, Have I Been Pwned ni un vrai SMTP.
- **Frontend (Vitest)** : redirection des pages privées, formulaires et messages d'erreur, glissement des panneaux, menu du compte, onglet Admin masqué aux non-admins, réglages de notifications.
- **Bout en bout (Playwright)** : parcours inscription → code lu dans Mailpit → accueil → déconnexion → connexion ; `layout.spec.ts` et `seo.spec.ts` étendus aux nouvelles pages (`noindex` pour les pages privées et d'authentification sauf `/connexion` et `/inscription`).

## 11. Découpage en branches

Une branche et une PR par étape, dans cet ordre :

1. **`comptes-socle`** : UUID et migration, sessions et CSRF, inscription et connexion par mot de passe, validation par code, mot de passe oublié, file d'envoi et mails C1 à C5, Mailpit, écran de connexion, protection des pages privées, reprise de « Moi ».
2. **`comptes-securite`** : connexion Google, Turnstile, limites de tentatives, Have I Been Pwned, en-têtes nginx, journal de sécurité.
3. **`comptes-admin`** : rôles, onglet Admin, Premium, clé Claude uniquement dans `.env`, `app_settings` et limite de coût, état de la configuration, `/documentation/` protégée, réglages utilisateur réorganisés (profil, appareils).
4. **`comptes-rgpd`** : pages légales, acceptation et version des CGU, export (C7), suppression (C6), durées de conservation et C8, registre des traitements.
5. **`notifications`** : préférences, alertes de prix, N1 à N6, désinscription en un clic.

Dès l'étape 1, la case CGU de l'inscription et les colonnes `terms_*` existent ; les liens pointent vers `/cgu` et `/confidentialite`, qui restent de simples pages provisoires jusqu'à l'étape 4. L'écran `/accepter-cgu` arrive aussi à l'étape 4. Rien n'est mis en ligne avant la fin de l'étape 4.

Chaque étape met à jour le guide utilisateur, la documentation admin et `CLAUDE.md` pour ce qui la concerne.
