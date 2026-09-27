# Assistant IA

L'assistant est **Claude**, le modèle d'IA d'Anthropic. Il répond en français, simplement, en s'appuyant sur les **vraies données de l'application** et sur l'actualité trouvée sur le web.

## Avant de commencer : la clé API

L'assistant a besoin d'une **clé API Anthropic** (payante à l'usage). Deux façons de la fournir :

- dans **Réglages → Assistant IA** : elle est chiffrée en base et n'est jamais réaffichée ;
- ou dans le fichier `.env`, variable `ANTHROPIC_API_KEY`.

Sans clé, l'assistant affiche un message qui explique comment en ajouter une.

## Deux façons de l'utiliser

### La page Assistant IA

- Vos **conversations** à gauche, avec leur **coût estimé**, et la discussion à droite.
- Des questions prêtes pour démarrer : « Analyse mon portefeuille », « Explique-moi le top 10 du moment », « Combien d'ordres me reste-t-il à passer cette année ? », « C'est quoi le PER, simplement ? ».

### Le panneau latéral ✨

Les boutons ✨ (top 10, fiche d'un titre) ouvrent un panneau à droite, avec le titre comme sujet et des questions prêtes : « Analyse cette action », « Pourquoi est-elle dans le top 10 ? », « Aurais-je dû l'acheter il y a une semaine ? », « Quels sont les risques ? ».

## Ce que Claude peut consulter

Pour répondre, Claude utilise des outils. Ils apparaissent pendant la réponse :

| Outil | Ce qu'il donne |
|---|---|
| Recherche de titres | Trouver une action par nom, ticker ou ISIN |
| Fiche du titre | Cours, score détaillé, fondamentaux, éligibilité |
| Historique des cours | Clôtures et indicateurs sur une période |
| Top 10 | Le classement du moment |
| Votre portefeuille | Positions, performance, compteur d'ordres |
| Simulation d'achat passé | « Si j'avais acheté pour X € à telle date » |
| Recherche web | L'actualité récente (3 recherches maximum par réponse) |

## Bon à savoir

- Les réponses s'affichent **en direct**, mot par mot.
- Si vous fermez l'onglet pendant une réponse, elle est tout de même enregistrée dans la conversation.
- Le **modèle** se choisit dans les Réglages : Opus 5 (recommandé), Sonnet 5 (plus rapide), Haiku 4.5 (économique) ou Fable 5.1 (le plus puissant, plus cher).
- Le coût affiché est une **estimation** d'après les tarifs publics.

!> L'assistant peut se tromper. Il n'est pas un conseiller en investissement agréé.
