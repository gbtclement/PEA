# Registre des traitements

Registre prévu par l'article 30 du RGPD. Il décrit chaque traitement de données personnelles fait par Cotalyx. Le tenir à jour quand une fonction change ce qui est collecté, pourquoi, par qui ou combien de temps.

**Responsable du traitement** : [À COMPLÉTER : nom ou société, adresse, contact].
**Dernière mise à jour** : 5 octobre 2026.

Mesures de sécurité communes à tous les traitements : HTTPS, mots de passe hachés (Argon2), jetons de session et de lien stockés sous forme d'empreinte, cookies `HttpOnly` et `SameSite`, protection CSRF, limites anti-abus, secrets uniquement dans `.env`, base PostgreSQL non exposée hors du serveur, sauvegardes [À COMPLÉTER].

## Comptes et authentification

| | |
|---|---|
| **Finalité** | Créer et sécuriser le compte, ouvrir les sessions, retrouver l'accès (mot de passe oublié, « Ce n'était pas moi ») |
| **Base légale** | Exécution du contrat (CGU) |
| **Personnes concernées** | Membres inscrits (18 ans et plus) |
| **Données** | Prénom, nom, adresse mail, empreinte du mot de passe, identifiant Google, rôle, Premium, version des CGU acceptée, sessions (appareil, IP, dernière activité), appareils connus, codes et liens (empreintes) |
| **Destinataires** | L'éditeur (administrateur) ; Google pour les comptes « Continuer avec Google » ; Cloudflare (Turnstile) pour la case anti-robots |
| **Transferts hors UE** | Google, Cloudflare : États-Unis, clauses contractuelles types ou cadre UE–États-Unis [À VÉRIFIER] |
| **Conservation** | Jusqu'à la suppression du compte, ou 3 ans sans connexion (mail 30 jours avant). Compte non validé : 7 jours. Sessions, codes et liens : jusqu'à leur expiration |
| **Sécurité** | Argon2, sessions révocables, blocage après 10 échecs, captcha après 3, vérification Have I Been Pwned par préfixe d'empreinte (k-anonymat) |

## Données saisies : ordres, favoris, réglages

| | |
|---|---|
| **Finalité** | Suivre son portefeuille PEA, ses favoris et ses frais de courtage |
| **Base légale** | Exécution du contrat (CGU) |
| **Personnes concernées** | Membres inscrits |
| **Données** | Ordres (date, sens, quantité, prix, frais, note), favoris, réglages de frais |
| **Destinataires** | L'éditeur ; le membre lui-même (export) |
| **Transferts hors UE** | Aucun |
| **Conservation** | Jusqu'à la suppression du compte, ou 3 ans sans connexion |
| **Sécurité** | Chaque requête filtre sur le compte connecté ; suppression en cascade avec le compte |

## Notifications par mail

| | |
|---|---|
| **Finalité** | Prévenir le membre des mouvements de ses titres et de son compteur d'ordres (notifications N1 à N6) |
| **Base légale** | Exécution du contrat (CGU), avec opposition possible à tout moment : préférences dans les Réglages, lien « Ne plus recevoir ce mail » en un clic |
| **Personnes concernées** | Membres inscrits |
| **Données** | Préférences de notification, alertes de prix, favoris et positions, titres déjà signalés |
| **Destinataires** | Brevo (envoi SMTP) |
| **Transferts hors UE** | Aucun annoncé par Brevo (hébergement dans l'UE) [À VÉRIFIER] |
| **Conservation** | Jusqu'à la suppression du compte ; titres déjà signalés : 7 jours |
| **Sécurité** | Lien de désinscription signé (jamais stocké) ; mails envoyés seulement aux adresses validées |

## Assistant IA

| | |
|---|---|
| **Finalité** | Répondre aux questions du membre Premium sur les titres, son portefeuille et la bourse |
| **Base légale** | Exécution du contrat (CGU) |
| **Personnes concernées** | Membres Premium |
| **Données** | Questions et réponses, données consultées par l'assistant (portefeuille, titres), coût mensuel |
| **Destinataires** | Anthropic (modèle Claude) |
| **Transferts hors UE** | Anthropic : États-Unis, clauses contractuelles types [À VÉRIFIER] ; rappelé sous la zone de saisie |
| **Conservation** | Conversations : jusqu'à leur suppression par le membre ou celle du compte. Coût mensuel : jusqu'à la suppression du compte |
| **Sécurité** | Clé API uniquement dans `.env` ; limite de coût mensuelle par membre |

## Abonnements et paiements

| | |
|---|---|
| **Finalité** | Vendre et gérer l'abonnement Premium : paiement, renouvellement, résiliation, mails P1 à P5, preuve des accords avant paiement |
| **Base légale** | Exécution du contrat (CGV) ; obligation légale pour les factures |
| **Personnes concernées** | Membres abonnés ou qui ont commencé un paiement |
| **Données** | Formule, statut et dates de l'abonnement, identifiants client et abonnement Stripe, accords (version des CGV, renonciation au droit de rétractation, date, IP tronquée). Jamais le numéro de carte : il est saisi chez Stripe |
| **Destinataires** | Stripe (Stripe Payments Europe, Irlande) : paiement, factures |
| **Transferts hors UE** | Stripe peut traiter des données aux États-Unis, clauses contractuelles types [À VÉRIFIER] |
| **Conservation** | Abonnement et accords : jusqu'à la suppression du compte ; événements Stripe traités : 30 jours ; factures chez Stripe : 10 ans (obligation comptable) |
| **Sécurité** | Clés Stripe uniquement dans `.env` ; webhook vérifié par signature ; aucune donnée de carte chez Cotalyx |

## Mails

| | |
|---|---|
| **Finalité** | Envoyer les mails du compte (codes, liens, alertes de sécurité, export prêt, suppression, avertissement d'inactivité) les mails de l'abonnement (P1 à P5) et les notifications N1 à N6 choisies par le membre |
| **Base légale** | Exécution du contrat (CGU) ; intérêt légitime pour les alertes de sécurité |
| **Personnes concernées** | Membres, et personnes en cours d'inscription |
| **Données** | Adresse mail, prénom, type et contenu du mail, statut d'envoi |
| **Destinataires** | Brevo (envoi SMTP) |
| **Transferts hors UE** | Aucun annoncé par Brevo (hébergement dans l'UE) [À VÉRIFIER] |
| **Conservation** | Historique des mails : 90 jours. Le contenu des mails à code ou à lien est effacé dès l'envoi. Après suppression du compte, l'adresse est remplacée par une empreinte et le contenu des mails est effacé |
| **Sécurité** | Connexion SMTP chiffrée ; limite d'envois par adresse et par IP |

## Sécurité et prévention des abus

| | |
|---|---|
| **Finalité** | Détecter et bloquer les attaques (essais de mots de passe, robots), garder une trace des événements de compte |
| **Base légale** | Intérêt légitime |
| **Personnes concernées** | Membres et visiteurs qui utilisent les formulaires de compte |
| **Données** | Journal de sécurité (type d'événement, IP, détails), compteurs anti-abus (empreintes de l'adresse ou de l'IP) |
| **Destinataires** | L'éditeur |
| **Transferts hors UE** | Aucun |
| **Conservation** | Journal de sécurité : 12 mois, sans lien vers un compte supprimé. Compteurs anti-abus : 1 jour |
| **Sécurité** | Adresses et IP des compteurs stockées sous forme d'empreinte ; purge automatique chaque nuit |

## Droits des personnes

- **Accès et portabilité** : export JSON depuis les Réglages (voir [Comptes](comptes.md#export-des-données)).
- **Rectification** : Réglages (profil, adresse mail).
- **Effacement** : « Supprimer mon compte » dans les Réglages, ou par l'administrateur (voir [Comptes](comptes.md#suppression-du-compte)).
- **Opposition, limitation, autres demandes** : au contact indiqué dans les mentions légales, réponse sous un mois.
- **Violation de données** : notification à la CNIL sous 72 h si elle présente un risque, et aux personnes si le risque est élevé.
