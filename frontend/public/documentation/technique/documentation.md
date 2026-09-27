# Modifier cette documentation

Cette documentation est un site [Docsify](https://docsify.js.org). Il affiche directement des fichiers Markdown dans le navigateur, sans étape de compilation.

## Où sont les fichiers ?

```text
frontend/public/documentation/
├── index.html        # configuration de Docsify (nom, recherche, plugins, couleurs)
├── _sidebar.md       # menu de gauche
├── README.md         # page d'accueil de la documentation
├── guide/            # guide d'utilisation
├── technique/        # documentation technique
└── vendor/           # Docsify et ses plugins, copiés localement (versions dans VERSIONS.md)
```

Comme le dossier est dans `frontend/public/`, Vite le copie tel quel dans le build. nginx le sert à l'adresse `/documentation/`, **en dehors** de l'application React.

## Ajouter une page

1. Créez le fichier Markdown, par exemple `guide/alertes.md`.
2. Ajoutez-le dans `_sidebar.md`.
3. Les liens entre pages partent **toujours de la racine de la documentation** : écrivez `[Score](technique/score.md)`, y compris depuis une page de `guide/`.

## Encadrés

```markdown
?> Information utile (encadré bleu).

!> Avertissement important (encadré rouge).
```

## Voir le résultat

- **Sans rien reconstruire** : `cd frontend && npm run dev`, puis http://localhost:5180/documentation/. Rechargez la page après chaque modification.
- **Dans l'application complète** : `docker compose up -d --build web`, puis http://localhost:8095/documentation/.

## Mettre à jour Docsify

Les fichiers de `vendor/` viennent de jsDelivr, avec des versions fixées. Pour changer de version, retéléchargez-les et mettez à jour `vendor/VERSIONS.md`. Retirez de `vue.css` la ligne `@import` vers Google Fonts, pour que la documentation reste utilisable hors ligne.

## Garder la documentation à jour

Quand une fonctionnalité change, mettez à jour la page du guide **et** la page technique concernées dans la même branche que le code.
