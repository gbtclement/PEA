# Modifier la documentation et le guide

L'application embarque deux sites [Docsify](https://docsify.js.org). Docsify affiche directement des fichiers Markdown dans le navigateur, sans étape de compilation.

| Site | Adresse | Public | Dans la navigation |
|---|---|---|---|
| **Guide utilisateur** | `/guide/` | Les utilisateurs : l'app et la bourse expliquées simplement, avec des exemples | Oui, en bas de la barre latérale |
| **Documentation admin** | `/documentation/` | La personne qui installe et fait évoluer l'app | Non, et en `noindex` |

## Où sont les fichiers ?

```text
frontend/public/
├── docsify/              # partagé : Docsify et plugins (versions dans VERSIONS.md),
│                         #   theme.css (couleurs) et back-to-app.js (lien de retour)
├── guide/
│   ├── index.html        # configuration Docsify du guide
│   ├── _sidebar.md       # menu du guide
│   ├── README.md         # accueil du guide
│   ├── app/              # une page par écran de l'application
│   └── bourse/           # comprendre la bourse (cours avec exemples)
└── documentation/
    ├── index.html        # configuration Docsify de la documentation admin
    ├── _sidebar.md       # menu
    └── *.md              # une page par sujet technique
```

Comme ces dossiers sont dans `frontend/public/`, Vite les copie tels quels dans le build. nginx les sert **en dehors** de l'application React.

## Quelle information va où ?

- **Guide** : ce que voit et fait l'utilisateur, le vocabulaire, des exemples chiffrés. Pas de nom de fichier, de commande, ni de variable d'environnement.
- **Documentation admin** : formules exactes, tâches planifiées, API, base, commandes, configuration.
- Le guide ne renvoie jamais vers la documentation admin. L'inverse est possible avec un lien absolu marqué `':ignore'`, par exemple `[guide](/guide/ ':ignore')`.

## Ajouter une page

1. Créez le fichier Markdown, par exemple `guide/bourse/fiscalite.md`.
2. Ajoutez-le dans le `_sidebar.md` du même site.
3. Les liens entre pages partent **toujours de la racine du site** : écrivez `[Le PEA](bourse/pea.md)`, y compris depuis une page de `app/`.

## Encadrés et pièges de syntaxe

```markdown
?> Information utile (encadré bleu).

!> Avertissement important (encadré rouge).
```

!> Dans un tableau, écrivez `&lt;` au lieu de `<` quand du **gras** suit sur la même ligne, sinon le gras ne s'affiche pas.

## Voir le résultat

- **Sans rien reconstruire** : `cd frontend && npm run dev`, puis http://localhost:5180/guide/ ou http://localhost:5180/documentation/. Rechargez la page après chaque modification.
- **Dans l'application complète** : `docker compose up -d --build web`, puis http://localhost:8095/guide/.
- **Tests** : `e2e/documentation.spec.ts` ouvre chaque page des deux sites et vérifie que les liens internes existent.

## Mettre à jour Docsify

Les fichiers de `docsify/` viennent de jsDelivr, avec des versions fixées. Pour changer de version :
1. retéléchargez-les ;
2. mettez à jour `docsify/VERSIONS.md` ;
3. retirez de `vue.css` la ligne `@import` vers Google Fonts, pour que les sites restent utilisables hors ligne.

## Garder la documentation à jour

Quand une fonctionnalité change, mettez à jour dans la même branche que le code :
- la page du **guide** concernée ;
- la page de la **documentation admin** concernée.
