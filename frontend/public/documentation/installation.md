# Installation et exploitation

## Ce qu'il faut installer

- **Docker Desktop** : il fait tourner la base de données, l'API, le worker et le site. Il doit être **démarré** avant de lancer l'application.
- **Git**, pour récupérer le code.
- **Node.js 22** seulement si vous voulez modifier l'interface (voir [Développement et tests](developpement.md)).

## Premier lancement

```bash
git clone https://github.com/gbtclement/PEA.git
cd PEA
cp .env.example .env
```

Ouvrez `.env` et remplacez `APP_SECRET=change-me` par une longue chaîne aléatoire. Par exemple, avec Node :

```bash
node -e "console.log(require('crypto').randomBytes(48).toString('base64url'))"
```

?> `APP_SECRET` signe les cookies temporaires de la connexion Google. Le changer interrompt seulement les connexions Google en cours.

La **clé Claude** de l'assistant se met dans `ANTHROPIC_API_KEY`, et nulle part ailleurs. Une clé saisie autrefois dans les Réglages a été effacée par la mise à jour des comptes : recopiez-la dans `.env`, puis `docker compose up -d api`. L'onglet Admin affiche « Renseigné » en face de Claude quand elle est lue.

L'**abonnement Premium** demande les quatre variables `STRIPE_…` : voir [Abonnement (Stripe)](abonnement.md#mise-en-place). Vides, la page Premium affiche « L'abonnement arrive bientôt. ».

Renseignez aussi les comptes et les mails :

| Variable | En local | En ligne |
|---|---|---|
| `ADMIN_EMAIL` | Votre adresse : ce compte devient administrateur | Idem |
| `COOKIE_SECURE` | `false` (le site local est en HTTP) | `true` (HTTPS obligatoire) |
| `SMTP_HOST` / `SMTP_PORT` | `mailpit` / `1025` | `smtp-relay.brevo.com` / `587` |
| `SMTP_USER` / `SMTP_PASSWORD` | vides | Identifiants SMTP de Brevo |
| `SMTP_TLS` | `none` | `starttls` |
| `MAIL_FROM` | `PEA Radar <no-reply@pea-radar.local>` | Une adresse de votre domaine, validée chez Brevo |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Vides (pas de bouton Google), ou le client OAuth ci-dessous | Client OAuth Google |
| `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET_KEY` | Vides (pas de case anti-robot) | Clés du widget Turnstile |
| `HIBP_ENABLED` | `true` (`false` hors connexion) | `true` |
| `HSTS_ENABLED` | `false` | `true`, une fois le HTTPS en place |
| `DEV_ORIGINS` | `http://localhost:5180` (serveur Vite) | Vide |

### Connexion avec Google (facultatif)

1. Dans la [console Google Cloud](https://console.cloud.google.com/apis/credentials), créez un projet, puis configurez l'**écran de consentement OAuth** (type « Externe », nom « PEA Radar », votre adresse de contact).
2. **Identifiants → Créer des identifiants → ID client OAuth**, type **Application Web**.
3. Dans **URI de redirection autorisés**, ajoutez :
   - en local : `http://localhost:8095/api/auth/google/callback` ;
   - en ligne : `https://<votre-domaine>/api/auth/google/callback`.

   Les « origines JavaScript autorisées » sont inutiles : tout passe par le serveur.
4. Copiez l'ID client et le code secret dans `GOOGLE_CLIENT_ID` et `GOOGLE_CLIENT_SECRET`, puis `docker compose up -d`.

L'adresse de retour est construite à partir de `PUBLIC_BASE_URL` : elle doit correspondre exactement à l'une des URI déclarées.

### Case anti-robot Cloudflare Turnstile (facultatif en local)

1. Dans le tableau de bord Cloudflare, ouvrez **Turnstile → Add widget** (gratuit, sans y déplacer votre domaine).
2. Nom « PEA Radar », mode **Managed**, domaines `localhost` et votre domaine public.
3. Copiez la **Site Key** dans `TURNSTILE_SITE_KEY` et la **Secret Key** dans `TURNSTILE_SECRET_KEY`.

Sans ces clés, les formulaires fonctionnent sans case anti-robot ; les limites de tentatives restent actives.

Lancez ensuite tout :

```bash
docker compose up -d --build
```

Puis ouvrez **http://localhost:8095**.

## Votre compte administrateur

Au démarrage, le compte `ADMIN_EMAIL` devient administrateur. Il n'a pas encore de mot de passe : un mail « Choisir un nouveau mot de passe PEA Radar » lui est envoyé, avec un lien valable 24 h.

- En local, ce mail arrive dans **Mailpit** : **http://localhost:8025**. Tous les mails de l'application y sont capturés, aucun ne part vraiment.
- Lien expiré ? Utilisez **Mot de passe oublié ?** sur l'écran de connexion.

Les autres personnes créent leur compte elles-mêmes avec **Créer un compte**. Détails dans [Comptes utilisateurs](comptes.md).

L'onglet **Admin** de la barre latérale n'apparaît que pour ce compte (et les autres admins). On y offre **Premium** à un compte (assistant IA et prévisions), on règle le modèle et la limite mensuelle de l'assistant, et on vérifie ce qui est renseigné dans `.env` (sans jamais afficher les valeurs), avec un bouton pour envoyer un mail de test.

## Mettre à jour une installation d'avant les comptes

La première reconstruction après l'arrivée des comptes applique une migration **à sens unique** : les identifiants des utilisateurs deviennent des UUID. **Sauvegardez d'abord** :

```bash
docker compose exec -T db pg_dump -U pea pea_radar > ../pea-sauvegarde.sql
```

Vérifiez que le fichier n'est pas vide, ajoutez les variables ci-dessus dans `.env`, puis `docker compose up -d --build`. Votre portefeuille, vos favoris, vos conversations et vos réglages sont repris par le compte `ADMIN_EMAIL`.

## Ce qui se passe au premier démarrage

Le **worker** remplit la base tout seul, dans cet ordre :

| Étape | Durée approximative |
|---|---|
| Liste des titres (Euronext, grands indices, ETF) | moins d'une minute |
| 5 ans d'historique de cours pour tous les titres | une dizaine de minutes |
| Premières prévisions et premiers scores (techniques seulement) | une à deux minutes |
| Données fondamentales (PER, dividende, dette…) | environ une heure |
| Scores complets, et donc **premier top 10** | juste après les fondamentaux |

Pendant ce temps, l'application fonctionne mais certaines pages sont vides ou partielles. En particulier, le **top 10 reste vide** jusqu'à la fin du chargement des fondamentaux : une action n'y entre que si au moins 60 % de son score est calculable, et la partie technique seule n'en représente que 50 %. En bas de la barre latérale, l'état du marché indique l'heure de la dernière mise à jour.

?> Des messages `possibly delisted` dans les journaux du worker sont normaux : ce sont des titres radiés de la cote que Yahoo ne connaît plus.

## Les jours suivants

- Allumez Docker Desktop : les conteneurs redémarrent automatiquement (`restart: unless-stopped`).
- Si le PC était éteint à 7 h, le worker **rattrape** au démarrage ce qui a pris du retard (liste des titres, historique, prévisions, fondamentaux).
- Pendant la séance (9 h – 17 h 35, jours ouvrés), les cours sont rafraîchis toutes les 1 à 5 minutes selon les titres, et les clôtures officielles sont chargées à 18 h 15.

## Commandes utiles

```bash
docker compose ps                  # état des conteneurs
docker compose logs -f worker      # suivre le travail du worker (et l'envoi des mails)
docker compose logs api | grep admin   # ligne de reprise du compte administrateur
docker compose stop                # tout arrêter (les données sont conservées)
docker compose up -d --build       # relancer après une mise à jour du code
```

!> `docker compose down -v` **efface la base de données** (volume `pgdata`) : comptes, ordres, favoris, conversations et réglages compris. Ne l'utilisez que pour repartir de zéro.
