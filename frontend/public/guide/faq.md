# Questions fréquentes

## Pourquoi PEA Radar s'appelle maintenant Cotalyx ?

L'application ne se limite plus au PEA : elle s'adresse à tous les investisseurs particuliers, quelle que soit leur enveloppe (PEA, compte-titres…). Le nouveau nom reflète ce changement ; vos comptes, favoris et ordres sont inchangés.

## Les cours sont-ils en temps réel ?

Non. Ils viennent d'une source gratuite, avec environ **15 minutes de retard**, et sont rafraîchis toutes les 1 à 5 minutes pendant la séance. Le soir, l'application charge les cours de clôture officiels. Au moment de passer un ordre, fiez-vous au cours affiché par votre banque. Voir [Fraîcheur des données](app/donnees.md).

## Pourquoi rien ne bouge le soir et le week-end ?

La bourse est fermée : aucun échange, donc aucun nouveau cours. L'application affiche les chiffres exacts de la dernière séance.

## Pourquoi une page est-elle vide ?

Juste après l'installation, l'application a besoin de temps pour tout charger : une dizaine de minutes pour les cours, environ une heure pour les données des entreprises. Le **top 10** n'apparaît qu'une fois ces données chargées. Si une page reste vide plus longtemps, prévenez la personne qui administre l'application.

## Pourquoi une action n'est-elle pas dans le top 10 malgré un bon score ?

Elle ne passe pas l'un des filtres : pas assez échangée, cotée depuis moins de 200 séances, éligibilité « à vérifier », ou trop de données manquantes. Voir [Page d'accueil](app/accueil.md).

## Pourquoi le score d'un ETF est-il différent ?

Un ETF n'a pas de bilan ni de bénéfices : seule la partie technique compte, ramenée sur 100. Voir [Comprendre le score](app/score.md).

## Le score me dit-il quoi acheter ?

Non. Il résume la situation **actuelle** de l'action pour vous aider à trier et à comprendre. Il ne prédit pas l'avenir. Voir [Risques et bonnes pratiques](bourse/risques.md).

## L'application passe-t-elle des ordres à ma place ?

Non, jamais. Elle ne se connecte pas à votre banque. Vous passez vos ordres chez votre banque, puis vous les enregistrez dans le Portefeuille.

## Les frais affichés sont-ils exacts ?

Ce sont les frais de courtage calculés avec la grille de vos Réglages. La **taxe sur les transactions financières**, due à l'achat de grandes entreprises françaises, n'est pas incluse. Corrigez le montant à la saisie en recopiant votre avis d'opéré. Voir [Passer un ordre](bourse/ordres-et-frais.md).

## Une action « Éligible » peut-elle être refusée par ma banque ?

C'est possible : l'éligibilité est déduite du pays du siège, pas d'une liste officielle. Vérifiez avant un achat important, et signalez un badge faux à l'administrateur du site (voir [Réglages](app/reglages.md)).

## Combien coûte l'assistant IA ?

Il est réservé aux membres **[Premium](app/premium.md)**, avec un budget par mois. Chaque question coûte en général quelques centimes ; le coût de chaque conversation et votre dépense du mois sont affichés. Voir [Assistant IA](app/assistant.md).

## Premium est-il obligatoire ?

Non. Presque tout Cotalyx est gratuit. Premium, payant, ajoute l'assistant IA et la liste des prévisions court terme. Voir [Premium](app/premium.md).

## Comment résilier Premium ?

Dans les **Réglages**, carte **Abonnement**, cliquez sur **Gérer mon abonnement**, puis résiliez dans l'espace client de Stripe. Voir [Premium](app/premium.md#gérer-ou-résilier).

## Suis-je remboursé si je résilie ?

Non : vous gardez Premium jusqu'à la fin de la période déjà payée (le mois ou l'année en cours), puis il s'arrête. Rien n'est prélevé ensuite.

## Cotalyx voit-il ma carte bancaire ?

Non. Le paiement se fait sur la page sécurisée de **Stripe**, notre prestataire de paiement : Cotalyx ne voit jamais votre numéro de carte.

## Je suis bloqué après plusieurs essais

Après **10 mots de passe faux** en 15 minutes, le compte est bloqué **15 minutes**, même avec le bon mot de passe : c'est ce qui empêche un pirate d'essayer des milliers de mots de passe. Attendez un quart d'heure, ou cliquez sur **Mot de passe oublié ?** pour en choisir un nouveau. Dès la 3ᵉ erreur, une case « Je ne suis pas un robot » s'affiche : cochez-la avant de réessayer. Voir [Votre compte](app/compte.md#se-connecter).

## Pourquoi mon mot de passe est-il refusé ?

Soit il fait moins de 12 caractères, soit il **apparaît dans des fuites de données connues** : il a déjà été volé sur un autre site, et les pirates l'essaient en premier. Choisissez une phrase de plusieurs mots que vous n'utilisez nulle part ailleurs. Voir [Choisir un bon mot de passe](app/compte.md#choisir-un-bon-mot-de-passe).

## Comment récupérer ou supprimer mes données ?

Dans les **Réglages**, carte **Mes données** : **Exporter mes données** prépare un fichier avec tout ce que vous avez saisi, et **Supprimer mon compte** efface tout, immédiatement et définitivement. Voir [Réglages](app/reglages.md#mes-données). Le détail de ce qui est conservé, et combien de temps, est dans la [politique de confidentialité](/confidentialite ':ignore').

## Comment ne plus recevoir un mail ?

Cliquez sur **Ne plus recevoir ce mail** en bas du mail : pas besoin de vous connecter, vous choisissez d'arrêter ce mail seulement ou toutes les notifications. Vous pouvez aussi tout régler dans les **Réglages**, carte **Notifications par mail** (voir [Réglages](app/reglages.md#notifications)). Les mails liés à votre compte (code, alerte de sécurité) continuent d'arriver.

## Mes données sont-elles envoyées quelque part ?

Tout reste sur l'ordinateur où tourne l'application. Seules exceptions :
- les demandes de cours envoyées à la source de données ;
- vos questions à l'assistant, envoyées à Anthropic avec les données que Claude consulte pour vous répondre ;
- les mails du compte (code, lien, alertes) et les notifications que vous avez choisies, envoyés par un service d'envoi de mails ;
- si vous utilisez **Continuer avec Google**, Google sait que vous vous connectez à Cotalyx ;
- la case « Je ne suis pas un robot » est vérifiée par Cloudflare ;
- pour savoir si un mot de passe a fuité, seuls les 5 premiers caractères de son empreinte partent vers le service Have I Been Pwned : jamais le mot de passe lui-même.
