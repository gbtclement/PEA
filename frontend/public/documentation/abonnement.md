# Abonnement Premium (Stripe)

Premium donne accès à l'**assistant IA** et aux **prévisions court terme** (liste des prédictions et bloc « Prévision » d'une fiche). Les signaux, le bilan des prévisions et tout le reste du site restent ouverts à tous les membres. Il s'obtient par un abonnement mensuel ou annuel, payé par carte via **Stripe**, sans période d'essai.

Code : `backend/app/services/billing/`, routes `backend/app/api/routes/billing.py`, tâches `backend/app/jobs/billing.py`. Spécification : `docs/superpowers/specs/2026-09-30-premium-stripe-design.md`.

## Qui est Premium

`premium_source()` (`services/billing/access.py`) décide, sans appeler Stripe, dans cet ordre :

| Source | Condition | Affiché dans l'onglet Admin |
|---|---|---|
| `admin` | rôle admin | Admin |
| `offered` | case **Premium offert** cochée par un admin (`users.is_premium`) | Offert |
| `subscription` | abonnement en état `active`, `past_due` (paiement en échec, Stripe relance) ou `trialing` | Abonné (mensuel) / Abonné (annuel) |
| `none` | aucun des trois | — |

`require_premium()` protège l'assistant et les deux routes de prévision (`403 premium_required`). `GET /api/me` renvoie `has_premium` et `premium_source`.

## Fonctionnement

1. **Page `/premium`** : prix lus chez Stripe (`GET /api/billing/plans`, gardés 1 heure en cache : un prix changé chez Stripe apparaît dans l'heure, ou tout de suite après un redémarrage de `api`), choix mensuel ou annuel avec l'économie de l'annuel. Deux cases obligatoires : acceptation des [CGV](/cgv ':ignore') et renonciation au droit de rétractation (accès immédiat). L'accord est enregistré dans `billing_consents` (version des CGV, date, IP tronquée) **avant** l'appel à Stripe.
2. **Stripe Checkout** : `POST /api/billing/checkout` crée une page de paiement Stripe et renvoie son adresse. 10 passages en caisse par compte et par heure au plus.
3. **Retour** sur `/premium/merci?session_id=…` : `POST /api/billing/sync` relit la session chez Stripe et active Premium sans attendre le webhook. Après 30 s sans activation, la page rassure : cela peut prendre quelques minutes.
4. **Webhook** `POST /api/billing/webhook` : Stripe prévient de chaque changement. Seule la signature (`STRIPE_WEBHOOK_SECRET`) compte ; chaque événement est traité une seule fois (`stripe_events`, gardé 30 jours). L'état d'un abonnement ne s'écrit **que** par `apply_subscription()` (`services/billing/state.py`), qui envoie aussi les mails.
5. **Gérer** : « Gérer mon abonnement » (Réglages, carte Abonnement) ouvre le **portail client Stripe** (`POST /api/billing/portal`) : carte, factures, changement de formule, résiliation.

Tâches du worker :

| Tâche | Quand | Rôle |
|---|---|---|
| `billing_sync` | 3 h 30 chaque nuit | Relit chez Stripe chaque abonnement vivant (et ceux terminés depuis moins de 7 jours) : rattrape un webhook perdu. Met aussi à jour l'adresse mail du client Stripe |
| `renewal_notices` | 9 h chaque jour | Mail P5, 30 jours avant le renouvellement d'un abonnement **annuel** non résilié, une fois par échéance |
| `stripe_cancellations` | Chaque minute | Résilie chez Stripe l'abonnement d'un compte supprimé, jusqu'à réussite (`stripe_cancellations`) |

Mails :

| | Type interne | Quand |
|---|---|---|
| P1 | `premium_started` | Abonnement activé : bienvenue, formule, prochaine échéance |
| P2 | `payment_failed` | Paiement en échec (`past_due`), une fois par facture : mettre à jour la carte ; l'accès continue pendant les relances |
| P3 | `premium_canceling` | Résiliation demandée : date de fin d'accès, possibilité d'annuler la résiliation avant |
| P4 | `premium_ended` | Accès terminé : lien pour se réabonner |
| P5 | `renewal_reminder` | 30 jours avant le renouvellement annuel (article L215-1 du Code de la consommation) |

Ce sont des mails du compte (pas des notifications N1 à N6) : ils partent toujours.

**Suppression d'un compte abonné** : `erase_account()` met l'abonnement vivant en file (`stripe_cancellations`) ; le worker le résilie immédiatement chez Stripe, sans remboursement (CGV, article 5).

## Mise en place

1. Créer un compte sur [stripe.com](https://stripe.com). Tout se fait d'abord en **mode test** (interrupteur en haut du tableau de bord).
2. **Produit** : Catalogue de produits > Ajouter un produit, nom « PEA Radar Premium », avec **deux prix récurrents** en EUR, TTC : un mensuel et un annuel. Copier l'identifiant de chaque prix (`price_…`).
3. **Portail client** : Paramètres > Facturation > Portail client. Autoriser la mise à jour de la carte, l'historique des factures, le changement de formule entre les deux prix, et la résiliation **en fin de période** (pas immédiate).
4. **E-mails clients** : Paramètres > E-mails clients : activer les reçus de paiement et les factures. PEA Radar n'envoie pas de facture lui-même.
5. **Webhook** : Développeurs > Webhooks > Ajouter un point de terminaison, adresse `https://<domaine>/api/billing/webhook`, événements :
   - `checkout.session.completed`
   - `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`
   - `invoice.paid`, `invoice.payment_failed`

   Copier le secret de signature (`whsec_…`).
6. Renseigner dans `.env` : `STRIPE_SECRET_KEY` (Développeurs > Clés API, `sk_test_…`), `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_MONTHLY`, `STRIPE_PRICE_YEARLY`. Les quatre sont nécessaires : s'il en manque une, la page `/premium` affiche « L'abonnement arrive bientôt. ».
7. Relancer : `docker compose up -d --build api worker`. L'onglet Admin, carte « État de la configuration », affiche « Paiement (Stripe) : Renseigné » et le mode (test ou réel).

## Tester en local

Avec la [CLI Stripe](https://docs.stripe.com/stripe-cli) :

```bash
stripe login
stripe listen --forward-to localhost:8095/api/billing/webhook
```

`stripe listen` affiche un `whsec_…` : le mettre dans `STRIPE_WEBHOOK_SECRET` (il remplace celui du tableau de bord tant que l'on teste en local), puis relancer `api` et `worker`.

- Carte acceptée : `4242 4242 4242 4242`, une date future, un CVC quelconque.
- Carte refusée au renouvellement (pour tester P2) : `4000 0000 0000 0341`.
- Pour avancer dans le temps (renouvellement, fin de période, rappel P5) : les **horloges de test** de Stripe (Facturation > Horloges de test).

## Passer en mode réel

1. Avoir un statut qui permet de vendre (au minimum une micro-entreprise avec un **SIRET**), et compléter les passages `[À COMPLÉTER]` des [CGV](/cgv ':ignore'), des CGU et des mentions légales.
2. Activer le compte Stripe (identité, compte bancaire).
3. Recréer le produit et ses deux prix en mode réel, et un nouveau webhook en mode réel (les objets du mode test ne passent pas en réel).
4. Mettre dans `.env` les clés `sk_live_…`, le nouveau `whsec_…` et les nouveaux `price_…`, puis relancer `api` et `worker`. L'onglet Admin affiche « mode réel ».

## Dépannage

- **État de la configuration** (onglet Admin) : « Paiement (Stripe) », le mode, et l'heure du **dernier webhook reçu**. Aucune clé n'est jamais affichée. Pas de webhook depuis longtemps alors que des abonnés paient : vérifier l'adresse et le secret du webhook chez Stripe (Développeurs > Webhooks montre les envois en échec).
- Journaux : `docker compose logs worker | grep -i stripe` et `docker compose logs api | grep -i stripe`.
- Un abonnement mal à jour se corrige seul à la synchronisation de 3 h 30.
- **Offrir Premium** sans paiement : onglet Admin, interrupteur **Premium offert** sur la ligne du membre.

## Rembourser

À la main, depuis le tableau de bord Stripe (Paiements > le paiement > Rembourser). L'application ne rembourse jamais elle-même ; pour couper l'accès, résilier l'abonnement dans Stripe.
