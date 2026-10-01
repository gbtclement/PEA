# Fiche d'un titre

On y arrive en cliquant sur un titre n'importe où dans l'application.

## En-tête

Le nom, le ticker, la place de cotation, le cours, la variation du jour et le badge d'éligibilité. Trois boutons :

- ⭐ **Favori** : le titre apparaît dans le filtre « favoris », et son cours est rafraîchi en priorité (toutes les minutes pendant la séance).
- ✨ **Demander à l'IA** : ouvre l'assistant avec ce titre comme sujet et des questions prêtes.
- 🔔 **Créer une alerte** : recevez un mail quand le cours passe **au-dessus** ou **en dessous** d'un prix que vous choisissez, dans la devise du titre (le cours actuel est proposé). Le mail part une seule fois, puis l'alerte se désactive : retrouvez-la dans les [Réglages](app/reglages.md#notifications) pour la réarmer ou la supprimer. Il faut être connecté.
- **+ J'ai acheté** : ouvre le formulaire d'ordre déjà rempli avec ce titre (voir [Portefeuille](app/portefeuille.md)).

## Graphique

Chaque bougie résume une période. Vert : le cours a monté ; rouge : il a baissé. Les barres en bas montrent les volumes échangés.

| Bouton | Ce que montre chaque bougie |
|---|---|
| 1J | 5 minutes de la dernière séance |
| 1S | 30 minutes sur une semaine |
| 1M, 6M, 1A, 5A | Une journée |

Vous pouvez aussi afficher :
- les **moyennes mobiles 50 et 200 jours**, qui lissent le cours pour faire ressortir la tendance ;
- le **RSI** et le **MACD**, deux indicateurs de dynamique affichés sous le graphique.

Tout est expliqué avec des exemples dans [Lire un graphique](bourse/analyse-technique.md).

## Cartes

| Carte | Contenu |
|---|---|
| **Score** | Les 8 composantes, avec les points obtenus sur le maximum et une phrase d'explication (voir [Comprendre le score](app/score.md)). Un badge « données incomplètes » apparaît s'il manque des informations. |
| **Données fondamentales** | PER, bénéfice par action, croissance, dette, marge, dividende, capitalisation (voir [Juger une entreprise](bourse/analyse-fondamentale.md)). |
| **Simulateur** | « Si j'avais investi X € il y a 1 semaine / 1 mois / 6 mois / 1 an » : gain en euros et en %, frais compris. |
| **Frais estimés** | Ce que coûterait un ordre avec votre grille de frais. |
| **Prévisions court terme** | Les signaux repérés aujourd'hui et la prévision à 1 jour, 1 semaine et 1 mois (voir [Prévisions](app/previsions.md)). |
| **Actualités** | Les derniers articles publiés sur l'entreprise. |

> **Exemple :** une action est passée de 40 € à 46 € en un an. Avec 12 actions achetées il y a un an, vous auriez payé 480 € plus 2,30 € de frais, soit 482,30 €. Elles valent aujourd'hui 552 € : un gain de 69,70 €, environ **+14 %**. Le simulateur fait ce type de calcul pour vous, frais compris.
