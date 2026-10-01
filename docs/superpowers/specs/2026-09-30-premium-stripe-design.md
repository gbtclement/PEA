# Abonnement Premium (Stripe) — conception

**Date :** 2026-09-30

**Suite de :** `docs/superpowers/specs/2026-09-28-comptes-utilisateurs-design.md` (§ 1.5 « Abonnement (plus tard) », § 4.3 Premium, § 6.1 `/cgv`).

**Demande de l'utilisateur :**
- un **abonnement Premium payant** par **Stripe** ;
- Premium donne accès à l'**assistant IA** et aux **Prévisions** ;
- deux formules : **mensuelle** et **annuelle** (moins chère au mois) ;
- **pas d'essai gratuit** (chaque question à l'assistant coûte un appel à l'API Claude).

**Décisions prises pendant la conception :**
- un membre gratuit voit le **bilan des prévisions passées** (onglets « bilan » et « statistiques des signaux ») ; la liste des prévisions et le bloc prévision de la fiche sont réservés à Premium ;
- paiement par **Stripe Checkout** (page hébergée par Stripe) et gestion par le **portail client Stripe** ; aucune donnée de carte ne passe par PEA Radar ;
- l'état de l'abonnement est tenu à jour par les **webhooks** Stripe et vérifié chaque nuit ;
- la bascule Premium de l'onglet Admin reste, renommée **« Premium offert »** ;
- les **prix** sont réglés dans Stripe et lus par l'API, jamais écrits dans le code ;
- nouvelle branche `premium`, partant de `notifications`.

## 1. Données

### 1.1 Table `subscriptions`

Une ligne au plus par utilisateur ; créée au premier paiement terminé, mise à jour **uniquement** à partir de l'état lu chez Stripe. Elle **reste après une résiliation** : un réabonnement réutilise le même client Stripe (les anciennes factures restent au même endroit).

| Colonne | Type | Remarque |
|---|---|---|
| `user_id` | UUID | clé primaire, clé étrangère `users.id` (`ON DELETE CASCADE`) |
| `stripe_customer_id` | texte | unique |
| `stripe_subscription_id` | texte, nullable | unique ; l'abonnement Stripe courant |
| `status` | texte | état Stripe : `active`, `past_due`, `canceled`, `unpaid`, `incomplete`, `incomplete_expired`, `trialing`, `paused` |
| `interval` | `month` \| `year`, nullable | formule |
| `current_period_end` | date/heure, nullable | fin de la période payée |
| `cancel_at_period_end` | booléen | résiliation demandée, effective à `current_period_end` |
| `renewal_notice_sent_for` | date/heure, nullable | `current_period_end` pour laquelle le rappel P5 est parti |
| `created_at`, `updated_at` | date/heure | |

### 1.2 Table `stripe_events`

`id` (identifiant de l'événement Stripe, clé primaire), `type`, `received_at`. Un événement déjà présent est ignoré (Stripe peut livrer deux fois le même). Purgée après 30 jours.

### 1.3 Table `billing_consents`

Preuve des accords donnés avant le paiement : `id` UUID, `user_id` (`ON DELETE CASCADE`), `cgv_version`, `withdrawal_waiver` (toujours vrai : sans lui, pas de paiement), `interval` choisi, `checkout_session_id` (nullable, rempli quand Stripe renvoie la session), `accepted_at`, IP tronquée.

### 1.4 `users.is_premium`

Garde sa colonne ; son sens devient **« Premium offert par l'admin »**. Aucune migration de données.

### 1.5 Qui est Premium

`User.has_premium` est vrai si **au moins une** condition est vraie :
1. rôle `admin` ;
2. `is_premium` (Premium offert) ;
3. une ligne `subscriptions` avec `status` dans `active`, `past_due`, `trialing`.

`past_due` garde l'accès pendant les relances de Stripe. `unpaid`, `canceled`, `incomplete`, `incomplete_expired`, `paused` ne donnent pas accès. `trialing` n'est jamais créé par PEA Radar (pas d'essai), mais reste accepté si un essai est ajouté à la main dans Stripe.

`has_premium` est calculé en une requête (relation chargée avec l'utilisateur), sans appel à Stripe.

## 2. Accès réservé

`require_premium()` (403 `premium_required`) protège :

| Route | Avant | Après |
|---|---|---|
| routes de l'assistant | Premium | Premium (inchangé) |
| `GET /api/forecasts` (liste) | connecté | **Premium** |
| `GET /api/securities/{id}/forecast` (bloc de la fiche) | connecté | **Premium** |
| `GET /api/forecasts/signals` | connecté | connecté (inchangé) |
| `GET /api/forecasts/track-record` | connecté | connecté (inchangé) |

Côté site, les endroits réservés affichent pour un membre gratuit une carte **« Réservé aux membres Premium »** avec un bouton **« Découvrir Premium »** vers `/premium` :
- `/assistant` (remplace le texte actuel « l'abonnement arrivera bientôt ») ;
- l'onglet des prévisions de `/previsions` ; les onglets bilan et statistiques restent affichés, et la page s'ouvre sur l'onglet bilan pour un membre gratuit ;
- le bloc prévision de la fiche titre.

Le site ne demande pas les données réservées quand l'utilisateur n'est pas Premium (pas de 403 inutile dans la console).

**Menu** : lien « Passer Premium » pour un membre gratuit ; badge « Premium » à côté du nom pour un membre Premium.

## 3. Parcours

### 3.1 Page `/premium` (publique)

- Présente Premium : l'assistant IA, la liste des prévisions, le bloc prévision des fiches ; lien vers le bilan des prévisions passées.
- Sélecteur **Mensuel / Annuel** ; les prix viennent de `GET /api/billing/plans` (montant, devise, intervalle, économie annuelle calculée par rapport à 12 mensualités), lus chez Stripe et gardés en cache 1 h.
- Bouton selon la personne :
  - visiteur : « Créer un compte » (vers `/inscription`, retour sur `/premium` après l'inscription si le mécanisme de redirection existant le permet) ;
  - connecté sans mail validé ou avec des CGU à ré-accepter : le parcours existant l'y envoie d'abord ;
  - connecté gratuit : **« S'abonner »** ;
  - abonné : « Vous êtes Premium » et « Gérer mon abonnement » ;
  - Premium offert ou admin : « Premium vous est offert », pas de bouton d'achat.
- Avant « S'abonner », **deux cases obligatoires** (le bouton reste désactivé sans elles) :
  - « J'ai lu et j'accepte les [CGV](/cgv) » ;
  - « Je demande l'accès immédiat à Premium et je renonce à mon droit de rétractation de 14 jours. »
- Stripe non configuré (clés absentes) : « L'abonnement arrive bientôt », boutons désactivés, prix masqués.
- Indexée par les moteurs de recherche (page vitrine) ; `/premium/merci` ne l'est pas.

### 3.2 Paiement

`POST /api/billing/checkout` `{interval, accept_cgv: true, waive_withdrawal: true}` (utilisateur validé, CSRF) :
1. refuse si l'utilisateur a déjà Premium : 409 `already_premium` (abonné) ou `premium_offered` (offert / admin) ;
2. refuse si une des cases manque : 422 `consent_required` ;
3. enregistre `billing_consents` ;
4. crée la session Stripe Checkout : mode abonnement, prix de la formule, client Stripe existant s'il y en a un (sinon Stripe le crée avec le mail du compte), `client_reference_id` = identifiant utilisateur, `metadata.user_id` sur la session et l'abonnement, langue `fr`, adresse de facturation demandée, `success_url` = `/premium/merci?session_id={CHECKOUT_SESSION_ID}`, `cancel_url` = `/premium` ;
5. renvoie `{url}` ; le site y redirige.

Stripe injoignable : 503 `billing_unavailable` « Paiement indisponible, réessayez dans quelques minutes » ; le consentement déjà enregistré reste (il ne donne aucun droit).

Limite : 10 sessions Checkout par utilisateur et par heure (429).

### 3.3 Retour : `/premium/merci`

- Appelle `POST /api/billing/sync` `{session_id}` : le serveur lit la session chez Stripe, vérifie qu'elle appartient à l'utilisateur connecté, et applique l'abonnement comme le ferait le webhook (utile si le webhook tarde ou ne passe pas en local).
- Puis relit `/api/me` toutes les 2 s jusqu'à `has_premium`.
- Affiche « Paiement reçu, activation en cours… », puis **« Bienvenue dans Premium »** avec des liens vers l'assistant et les prévisions.
- Après 30 s sans activation : « L'activation peut prendre quelques minutes ; vous recevrez un mail de confirmation. »
- Annulation sur la page Stripe : retour sur `/premium`, rien n'a changé.

### 3.4 Réglages : carte « Abonnement »

Dans `/reglages`, ancre `#abonnement` :
- abonné : formule, état, prochaine échéance (« Renouvellement le … ») ou « Premium s'arrête le … » si résilié ; bouton **« Gérer mon abonnement »** ;
- `past_due` : alerte « Le dernier paiement a échoué. Mettez à jour votre carte pour garder Premium. » ;
- Premium offert / admin : « Premium vous est offert » ;
- gratuit : « Vous n'êtes pas abonné » et lien vers `/premium` ; si un ancien abonnement existe, « Gérer mon abonnement » reste proposé (factures).

`POST /api/billing/portal` (utilisateur validé, CSRF) : crée une session du portail client Stripe pour le client de l'utilisateur (404 `no_customer` s'il n'en a pas), `return_url` = `/reglages#abonnement`, renvoie `{url}`.

Le portail Stripe (configuré dans le tableau de bord Stripe, voir § 7) permet : changer de carte, voir et télécharger les factures, passer de mensuel à annuel et inversement, résilier **à la fin de la période**.

### 3.5 Changement de mail

Quand un utilisateur qui a un client Stripe change de mail (lui-même ou par l'admin), le mail du client Stripe est mis à jour. Un échec est journalisé et rattrapé par la synchronisation de nuit ; il ne bloque pas le changement.

## 4. Webhooks et synchronisation

### 4.1 `POST /api/billing/webhook`

- Corps brut ; signature `Stripe-Signature` vérifiée avec `STRIPE_WEBHOOK_SECRET` (tolérance 5 min). Signature absente ou fausse : 400, rien n'est appliqué.
- Pas de cookie, pas de CSRF, pas de limite de débit.
- Événement déjà dans `stripe_events` : 200, ignoré.
- Types traités : `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`. Les autres : 200, ignorés.
- Pour chaque événement traité, on **relit l'abonnement chez Stripe** et on applique cet état (§ 4.2) : l'ordre d'arrivée des événements n'a pas d'importance.
- L'utilisateur est retrouvé par `metadata.user_id` (ou `client_reference_id`), sinon par `stripe_customer_id`. Utilisateur introuvable (compte supprimé entre-temps) : événement noté, 200, et l'abonnement Stripe est résilié tout de suite.
- Erreur pendant le traitement : 500 (Stripe réessaie) et l'événement n'est pas marqué traité.

### 4.2 Appliquer un état (`apply_subscription`)

Une seule fonction, utilisée par le webhook, `/api/billing/sync` et la synchronisation de nuit. Elle écrit la ligne `subscriptions`, compare l'accès avant et après, et déclenche :

| Changement | Effet |
|---|---|
| sans accès → avec accès (abonnement) | mail **P1**, événement `subscription_started` |
| `cancel_at_period_end` passe à vrai | mail **P3** |
| `cancel_at_period_end` repasse à faux (résiliation annulée dans le portail) | rien (le portail affiche la confirmation) |
| passe à `past_due` | mail **P2** (une fois par facture en échec, via `dedupe_key`) |
| avec accès → sans accès | mail **P4**, événement `subscription_ended` |

Un utilisateur qui a Premium offert reçoit P1 à P4 normalement (ils parlent de son abonnement payant).

### 4.3 Synchronisation de nuit (worker)

Chaque nuit à 03:30 (heure de Paris), le worker relit chez Stripe chaque abonnement dont `status` n'est pas `canceled` ni `incomplete_expired`, plus ceux terminés depuis moins de 7 jours, et applique l'état. Il met aussi à jour le mail des clients Stripe (§ 3.5). Stripe non configuré : la tâche ne fait rien.

## 5. Mails

Mails **de compte** (non désinscriptibles), même gabarit et même file d'envoi que C1…C8 (`email_log`, `dedupe_key`).

| Code | Déclenchement | Contenu |
|---|---|---|
| P1 | abonnement activé | bienvenue, ce que contient Premium, formule et prochaine échéance, lien « Gérer mon abonnement » |
| P2 | paiement échoué (`past_due`) | mettre à jour la carte ; l'accès continue pendant les relances de Stripe |
| P3 | résiliation demandée | confirmation, date de fin d'accès, possibilité d'annuler la résiliation avant cette date |
| P4 | accès terminé | Premium s'est arrêté ; lien pour se réabonner |
| P5 | 30 jours avant le renouvellement **annuel** (non résilié) | rappel du prix et de la date du prochain prélèvement, lien pour résilier |

P5 : tâche quotidienne du worker (09:00, heure de Paris) ; envoyé si `interval = year`, `status = active`, `cancel_at_period_end` faux, `current_period_end` dans 30 jours ou moins, et `renewal_notice_sent_for` différent de `current_period_end`. Rappel exigé pour la reconduction tacite des contrats de service (article L215-1 du Code de la consommation) ; pas de rappel pour la formule mensuelle.

Les **factures et reçus** sont envoyés par Stripe (réglage du tableau de bord, § 7).

## 6. Admin, configuration, journal

- **Onglet Admin** : la colonne Premium affiche « Abonné (mensuel) », « Abonné (annuel) », « Offert », « Admin » ou rien ; l'interrupteur devient « Premium offert ». La fenêtre « Modifier » montre l'état de l'abonnement en lecture seule. Supprimer un utilisateur abonné résilie son abonnement (§ 8).
- **État de la configuration** : « Stripe : configuré oui / non » (les 4 variables présentes), mode **test / réel** (déduit du préfixe de la clé, sans l'afficher), date du dernier webhook reçu. **Jamais les valeurs.**
- **Journal de sécurité** : nouveaux types `subscription_started`, `subscription_ended`, `billing_consent`.

## 7. `.env` et réglages Stripe

Nouvelles variables (vides par défaut) :

| Variable | Rôle |
|---|---|
| `STRIPE_SECRET_KEY` | clé secrète (`sk_test_…` ou `sk_live_…`) |
| `STRIPE_WEBHOOK_SECRET` | secret de signature du webhook (`whsec_…`) |
| `STRIPE_PRICE_MONTHLY` | identifiant du prix mensuel (`price_…`) |
| `STRIPE_PRICE_YEARLY` | identifiant du prix annuel (`price_…`) |

Stripe est « configuré » quand les quatre sont remplies.

La documentation admin explique, étape par étape : créer le produit « PEA Radar Premium » et ses deux prix récurrents (TTC, EUR) ; configurer le portail client (carte, factures, changement de formule, résiliation en fin de période) ; activer l'envoi des reçus et factures par Stripe ; déclarer l'adresse du webhook et les 6 événements ; tester en **mode test** (carte `4242 4242 4242 4242`, carte refusée `4000 0000 0000 0341`) avec **Stripe CLI** (`stripe listen --forward-to localhost:8095/api/billing/webhook`) ; passer en mode réel.

La bibliothèque Python officielle `stripe` est ajoutée ; tout appel à Stripe passe par un seul module (`services/billing/stripe_gateway.py`), remplacé par un faux dans les tests.

## 8. RGPD et textes légaux

- **Suppression de compte** : l'abonnement Stripe actif est **résilié immédiatement** (sans remboursement au prorata, comme les CGV le prévoient) avant l'effacement ; les lignes `subscriptions` et `billing_consents` sont effacées. Le client Stripe et ses factures restent chez Stripe (obligation comptable de 10 ans). Stripe injoignable : la suppression attend (même mécanisme de nouvelle tentative que le mail C6), l'utilisateur voit « Suppression en cours ».
- **Export** : ajoute `abonnement` (formule, état, dates, résiliation demandée) et `accords_de_vente` (version des CGV, date, renonciation) ; jamais les identifiants Stripe.
- **Conservation** : `stripe_events` 30 jours ; `subscriptions` et `billing_consents` tant que le compte existe.
- **`/cgv` (nouvelle page, brouillon)** : éditeur `[À COMPLÉTER]` ; objet et contenu de Premium ; prix (renvoi à `/premium`, TTC, mention de TVA `[À VÉRIFIER]`) ; paiement par Stripe ; durée, reconduction tacite et rappel annuel ; résiliation à tout moment depuis le portail, effective à la fin de la période payée, sans remboursement au prorata ; **renonciation au droit de rétractation** (article L221-28 13° du Code de la consommation) ; suspension en cas d'impayé ; disponibilité du service et évolution des prévisions ; **rien n'est un conseil en investissement** ; médiateur de la consommation `[À COMPLÉTER]` ; droit applicable.
- **CGU et confidentialité** : Stripe ajouté aux sous-traitants (Stripe Payments Europe, Irlande) ; données gardées par PEA Radar (état de l'abonnement, accords) et jamais vues (carte bancaire) ; nouvelle version des CGU (`TERMS_VERSION`), donc ré-acceptation par tous.
- **Registre** : nouveau traitement « Abonnements et paiements » (base légale : exécution du contrat ; obligation légale pour les factures).
- **Pied de page** : lien « CGV ».
- **Avant la mise en ligne** : vendre demande un statut (au minimum micro-entreprise avec SIRET), nécessaire aussi pour activer le mode réel de Stripe ; relecture des CGV par un professionnel conseillée.

## 9. API (résumé)

| Méthode | Route | Accès |
|---|---|---|
| GET | `/api/billing/plans` | public ; `{configured, plans: [{interval, amount, currency}], yearly_saving_pct}` |
| GET | `/api/billing/subscription` | connecté ; état affiché par la carte Abonnement (`source`: `subscription` \| `offered` \| `admin` \| `none`) |
| POST | `/api/billing/checkout` | validé + CSRF |
| POST | `/api/billing/sync` | validé + CSRF |
| POST | `/api/billing/portal` | validé + CSRF |
| POST | `/api/billing/webhook` | signature Stripe |

`/api/me` ajoute `premium_source` (`subscription` \| `offered` \| `admin` \| `none`) à côté de `has_premium`.

## 10. Tests

- **Serveur** (faux Stripe, aucun appel réseau) :
  - `has_premium` pour admin, offert, chaque état Stripe ;
  - 403 `premium_required` sur la liste des prévisions et le bloc de fiche, 200 sur bilan et statistiques pour un gratuit ;
  - checkout : cases manquantes, déjà abonné, Premium offert, Stripe non configuré, Stripe injoignable, réutilisation du client, limite de débit ;
  - webhook : signature fausse ou absente, événement en double, événements dans le désordre, utilisateur introuvable, type ignoré ;
  - `apply_subscription` : chaque ligne du tableau § 4.2 et ses mails ;
  - sync : session d'un autre utilisateur refusée ;
  - synchronisation de nuit et rappel P5 (annuel seulement, une seule fois par échéance, pas si résilié) ;
  - portail : sans client ;
  - suppression de compte avec abonnement actif, export, purge de `stripe_events` ;
  - état de la configuration sans valeurs.
- **Site** : `/premium` (prix, cases obligatoires, chaque cas de bouton, Stripe non configuré), `/premium/merci` (attente, succès, délai), carte Abonnement (chaque état), cartes « Réservé Premium » sans requête des données réservées, lien et badge du menu, colonne Admin.
- **De bout en bout** : un membre gratuit voit la carte Premium sur `/previsions` et sur une fiche, et le bilan ; `/premium` affiche « L'abonnement arrive bientôt » sans Stripe ; `/cgv` est accessible. Le paiement réel se teste à la main en mode test (§ 7).

## 11. Hors périmètre

Essai gratuit, codes promo, remboursements (faits à la main dans Stripe), TVA automatique (Stripe Tax), plusieurs devises, abonnements d'équipe, facturation dans PEA Radar.
