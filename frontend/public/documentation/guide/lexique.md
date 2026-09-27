# Lexique et questions fréquentes

## Lexique

| Terme | Explication simple |
|---|---|
| **PEA** | Plan d'épargne en actions : compte-titres qui permet, après 5 ans, de ne pas payer d'impôt sur le revenu sur les gains (les prélèvements sociaux restent dus). Il n'accepte que des actions d'entreprises européennes et certains ETF. |
| **Action** | Une part d'une entreprise. |
| **ETF** | Fonds coté en bourse qui reproduit un indice entier (ex. CAC 40, MSCI World). Diversifié en un seul achat. |
| **Ticker** | Le code court d'un titre en bourse (ex. `MC.PA` pour LVMH à Paris chez Yahoo). |
| **ISIN** | Identifiant international unique d'un titre (ex. `FR0000121014`). Les 2 premières lettres indiquent le pays du siège. |
| **Indice** | Panier d'actions qui résume un marché : CAC 40 (40 plus grandes françaises), SBF 120, Euro Stoxx 50. |
| **Capitalisation** | Valeur totale de l'entreprise en bourse : cours × nombre d'actions. |
| **Liquidité** | Facilité à acheter ou vendre un titre. Mesurée ici par le montant échangé chaque jour. |
| **Chandelier** | Représentation d'une séance : ouverture, plus haut, plus bas, clôture. Vert si le cours a monté, rouge s'il a baissé. |
| **Moyenne mobile (MM50, MM200)** | Moyenne des 50 ou 200 derniers cours de clôture. Un cours au-dessus de sa MM200 indique une tendance de fond haussière. |
| **RSI** | Indicateur de 0 à 100 qui mesure la vitesse des variations récentes. Au-dessus de 70 : le titre a beaucoup monté (surachat). Sous 30 : il a beaucoup baissé (survente). |
| **MACD** | Écart entre deux moyennes mobiles exponentielles (12 et 26 jours), comparé à sa propre moyenne (ligne de signal). Quand le MACD passe au-dessus de son signal, la dynamique devient haussière. |
| **PER** | Prix / bénéfice par action. Combien d'années de bénéfices « coûte » l'action. Un PER bas peut être une bonne affaire… ou une entreprise en difficulté. |
| **BPA** | Bénéfice par action. |
| **Rendement du dividende** | Dividende annuel / cours. 3 % = 3 € par an pour 100 € investis. |
| **PRU** | Prix de revient unitaire : ce qu'a coûté en moyenne chaque titre détenu, frais inclus. |
| **Plus-value latente / réalisée** | Latente : gain « sur le papier » sur les titres encore détenus. Réalisée : gain encaissé lors d'une vente. |
| **Séance** | Une journée de bourse (9 h – 17 h 30 à Paris, jours ouvrés hors fériés). |

## Questions fréquentes

### Les cours sont-ils en temps réel ?

Non. Ils viennent de Yahoo Finance, gratuitement, avec **15 à 20 minutes de retard**, et sont rafraîchis toutes les 2 à 30 minutes selon les titres. Pour passer un ordre, fiez-vous au cours affiché par votre banque.

### Pourquoi une page est vide ?

Au premier démarrage, le worker a besoin de temps (voir [Démarrer](guide/demarrer.md)). Sinon, regardez l'état du marché en bas de la barre latérale et les journaux : `docker compose logs -f worker`.

### Pourquoi une action n'est-elle pas dans le top 10 malgré un bon score ?

Elle ne passe peut-être pas les filtres : pas assez échangée, historique trop court, éligibilité « à vérifier » ou trop de données manquantes. Voir [Score mixte](technique/score.md).

### Pourquoi le score d'un ETF est-il différent ?

Les ETF n'ont pas de bilan ni de bénéfices : seule la partie technique compte, ramenée sur 100.

### L'application passe-t-elle des ordres ?

Non, jamais. Elle ne se connecte pas à votre banque. Vous saisissez vos ordres à la main après les avoir passés.

### Mes données sont-elles envoyées quelque part ?

Tout reste sur votre PC, dans la base PostgreSQL de Docker. Seules exceptions : les requêtes de cours vers Yahoo, et vos questions à l'assistant, envoyées à Anthropic avec les données que Claude consulte pour répondre.
