# Réglages

Les Réglages regroupent votre compte, votre abonnement, vos enveloppes et vos frais de courtage.

## Profil

Votre prénom et votre nom, tels qu'ils apparaissent dans l'application et dans les mails.

## Abonnement

La carte **Abonnement** montre votre formule Premium (mensuelle ou annuelle) et la date du prochain renouvellement, ou la date de fin si vous avez résilié. Une alerte apparaît si un paiement a échoué. Le bouton **Gérer mon abonnement** ouvre l'espace client de Stripe : carte, factures, changement de formule, résiliation. Voir [Premium](app/premium.md#gérer-ou-résilier).

Sans abonnement, la carte propose **Découvrir Premium**. Si l'administrateur vous offre Premium, elle l'indique.

## Mot de passe

Saisissez le mot de passe actuel, puis le nouveau (12 caractères au moins). Une jauge indique sa solidité. Après le changement, **tous vos autres appareils sont déconnectés** et un mail vous prévient.

Si vous avez créé votre compte avec Google, vous n'avez pas de mot de passe : la carte propose **Ajouter un mot de passe**, pour pouvoir aussi vous connecter avec votre adresse mail.

## Adresse mail

Saisissez la nouvelle adresse et votre mot de passe. Un **code à 6 chiffres** est envoyé à la nouvelle adresse : tapez-le pour valider le changement : vos autres appareils sont alors déconnectés, et l'ancienne adresse reçoit un mail de prévention.

## Appareils connectés

La liste de vos connexions ouvertes : appareil, navigateur et dernière activité. **Cet appareil** désigne celui que vous utilisez. Vous pouvez déconnecter un appareil que vous ne reconnaissez pas, ou **tous les autres** d'un coup.

?> Un appareil inconnu dans la liste ? Déconnectez-le, puis changez votre mot de passe.

## Notifications

Carte **Notifications par mail** : un interrupteur par mail, enregistré dès que vous cliquez.

| Mail | Par défaut | Quand |
|---|---|---|
| **Forte variation d'un titre suivi** | Activé | Pendant la séance, quand un favori ou une position bouge d'au moins le seuil choisi. Une fois par titre et par jour |
| **Alertes de prix** | Activé | Quand un titre franchit le prix choisi sur sa fiche |
| **Récap du soir** | Désactivé | À 18 h 45 les jours de bourse : valeur du portefeuille, variation du jour, hausses et baisses de vos favoris |
| **Récap de la semaine** | Désactivé | Le samedi à 9 h : performance, entrées et sorties du top 10, prévisions vérifiées |
| **Rappel du compteur d'ordres** | Activé | Les 1er octobre, novembre et décembre, s'il vous manque des ordres pour éviter les frais de votre banque |
| **Changement de score d'un favori** | Désactivé | Après la séance : entrée ou sortie du top 10, ou score qui bouge d'au moins 10 points |

- **Seuil de forte variation** : de 1 à 50 %, 5 % par défaut. Il est enregistré quand vous quittez le champ ; une virgule est acceptée (« 3,5 »).
- **Alertes de prix** : la liste de vos alertes, créées depuis la [fiche d'un titre](app/fiche-titre.md). Une alerte déclenchée affiche sa date : **Réarmer** la relance après vous avoir laissé choisir un nouveau prix (le cours est souvent resté près de l'ancien seuil), **Supprimer** l'efface. 50 alertes actives au plus.
- **Ne plus recevoir ce mail** : chaque notification se termine par ce lien. Il marche sans vous connecter : vous choisissez d'arrêter ce mail seulement, ou toutes les notifications.

Les mails liés à votre compte (codes, alertes de sécurité) sont toujours envoyés.

## Mes données

- **Exporter mes données** : cliquez, puis attendez le mail « Vos données Cotalyx sont prêtes » (en général moins d'une minute). Un lien **Télécharger mes données** apparaît dans la carte : c'est un fichier JSON, lisible par un autre logiciel. Il reste disponible **7 jours** ; un export par jour au plus. Si un export échoue, un message le dit et vous pouvez en demander un nouveau tout de suite.
- **Supprimer mon compte** : retapez votre adresse mail et votre mot de passe, puis cliquez sur **Supprimer définitivement**. Votre compte, vos ordres, vos favoris, vos conversations et vos réglages sont effacés tout de suite, sans retour possible.

Si vous vous connectez uniquement avec Google, vous n'avez pas de mot de passe : cliquez sur **Se reconnecter avec Google**, puis confirmez la suppression dans les **5 minutes**.

!> Pensez à exporter vos données **avant** de supprimer votre compte si vous voulez garder votre historique d'ordres.

## Mes enveloppes

Indiquez les comptes sur lesquels vous investissez :

| Case | Ce que vous verrez |
|---|---|
| **PEA** | Les actions et ETF qu'on peut loger dans un PEA (siège dans l'UE ou l'EEE) |
| **PEA-PME** | Les actions de petites et moyennes entreprises européennes (estimation) |
| **Compte-titres** | Tous les titres |

Si vous ne cochez rien, ou si vous cochez le compte-titres, vous voyez **tous les titres**. Sinon, un titre doit être compatible avec au moins une des enveloppes cochées.

Vos enveloppes s'appliquent :
- au **top 10** de l'accueil, aux plus fortes hausses et baisses, et à la carte du marché ;
- aux **prévisions** (case « Mes enveloppes uniquement », cochée par défaut) ;
- aux **mails** du samedi et « entrée dans le top 10 », qui suivent votre propre top 10 ;
- à l'**assistant**, qui en tient compte dans ses réponses.

L'Explorer montre toujours tous les titres : son filtre **Enveloppe** restreint à la demande. Les badges sont déduits automatiquement : voir [Le PEA](bourse/pea.md).

## Frais et compteur d'ordres

Les valeurs par défaut ne sont qu'un exemple : la formule **Invest Store Intégral** du Crédit Agricole. Remplacez-les par celles de votre courtier (brochure tarifaire de votre banque).

| Réglage | Par défaut |
|---|---|
| Ordres minimum par an | 12 |
| Frais si l'objectif n'est pas atteint | 96 € |
| Grille de frais | 0,48 % jusqu'à 500 € · 0,18 % jusqu'à 1 000 € · 0,12 % au-delà |

!> Le taux de la tranche s'applique au **montant total** de l'ordre. Un ordre de 510 € coûte donc **moins** qu'un ordre de 490 € : voir [Passer un ordre et payer moins de frais](bourse/ordres-et-frais.md).

Cette grille sert partout : frais proposés à la saisie d'un ordre, simulateur, estimation sur la fiche d'un titre, calcul « après frais » des prévisions.

## Corrections d'enveloppe

Les badges d'enveloppe (PEA, PEA-PME) sont communs à tous les membres : seul l'**administrateur** du site peut les corriger, depuis son onglet Admin. Si un badge vous semble faux, par exemple si votre banque refuse dans votre PEA une action marquée « PEA », signalez-le à l'administrateur. Sa correction est **toujours prioritaire** et n'est jamais écrasée par les mises à jour automatiques.
