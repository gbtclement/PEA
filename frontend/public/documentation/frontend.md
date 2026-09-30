# Frontend

Code : `frontend/src/`. Application monopage React construite avec Vite.

## Stack

| Besoin | Bibliothèque |
|---|---|
| Interface | React 19, TypeScript |
| Navigation | react-router 7 (`app/router.tsx`, pages chargées à la demande) |
| Données serveur | TanStack Query (cache, rafraîchissement automatique en séance) |
| Tableaux | TanStack Table et TanStack Virtual (fluide avec plus de 1 000 lignes) |
| Style | Tailwind CSS 4, composants shadcn/ui (`components/ui/`) |
| Graphique d'un titre | Lightweight Charts (TradingView) |
| Autres graphiques | ECharts (carte du marché, répartition, évolution du portefeuille) |
| Réponses de l'assistant | Rendu Markdown |
| Tests | Vitest, Testing Library, Playwright |
| Qualité | oxlint, `tsc -b` |

## Organisation

```text
src/
├── app/                  # Layout, Sidebar, AccountMenu, SignUpBanner, MarketStatus, router, NotFoundPage
├── components/           # DataTable, ScoreGauge, Sparkline, FavoriteButton, charts/EChart, ui/
├── features/
│   ├── auth/             # Écrans de compte, useMe, RequireAuth
│   ├── legal/            # CGU, confidentialité, mentions légales
│   ├── home/             # Accueil
│   ├── screener/         # Explorer et ETF (filtres dans l'URL)
│   ├── security/         # Fiche d'un titre et ses cartes
│   ├── forecasts/        # Prévisions (3 vues)
│   ├── portfolio/        # Portefeuille, formulaire d'ordre
│   ├── assistant/        # Page, panneau latéral, flux SSE (useChat)
│   ├── settings/         # Réglages
│   ├── explorer/, favorites/
├── lib/
│   ├── api/client.ts     # client HTTP typé
│   ├── api/schema.d.ts   # GÉNÉRÉ depuis l'OpenAPI : ne pas modifier à la main
│   ├── format.ts         # nombres, %, €, dates en français
│   └── colors.ts
└── seo/                  # usePageMeta et schema.org
```

Chaque dossier `features/<domaine>/` contient la page, ses composants et leurs tests (`*.test.tsx`).

## Routes

| Adresse | Page |
|---|---|
| `/` | Accueil |
| `/explorer` | Explorer (actions) |
| `/etf` | ETF |
| `/previsions` | Prévisions (`?vue=` pour l'onglet) |
| `/portefeuille` | Portefeuille |
| `/assistant` | Assistant IA |
| `/titres/:id` | Fiche d'un titre |
| `/reglages` | Réglages |
| `/connexion`, `/inscription` | Écran de compte à panneau glissant, hors de la mise en page (`?suite=` : page où revenir) |
| `/verifier-email`, `/mot-de-passe-oublie`, `/reinitialiser`, `/ce-n-etait-pas-moi` | Code, mot de passe oublié, nouveau mot de passe, « Ce n'était pas moi » |
| `/cgu`, `/confidentialite`, `/mentions-legales` | Pages légales (textes provisoires) |

`/previsions`, `/portefeuille`, `/assistant` et `/reglages` sont enveloppées par `RequireAuth` : un visiteur est renvoyé vers `/connexion?suite=…`. `useMe()` donne le compte connecté, ou `null` pour un visiteur.
| `/guide/` | Guide utilisateur (lien en bas de la barre latérale). Fichiers statiques servis par nginx, **hors** du routeur React |
| `/documentation/` | Cette documentation admin, **non liée** dans la navigation. Même fonctionnement |

## Conventions d'interface

- Thème clair, **bureau uniquement** : utilisable dès 1024 px, sur deux colonnes à partir de `xl` (1280 px).
- Les enfants d'une grille ont besoin de `min-w-0`. Les cartes shadcn ont `overflow-hidden` : vérifiez qu'aucune n'est coupée. Le test `e2e/layout.spec.ts` contrôle de 1100 à 1440 px.
- Un seul `h1` par page. `CardTitle` rend un `h2`, un sous-titre dans une carte est un `h3`.
- Chiffres en `tabular-nums`, vert pour la hausse, rouge pour la baisse.
- Textes visibles en **français**, identifiants de code en anglais.

## Types de l'API

```bash
# l'API de dev doit tourner sur :8000
cd frontend && npm run gen:api
```

## En développement

`npm run dev` lance Vite sur http://localhost:5180. Vite relaie `/api`, `/robots.txt`, `/sitemap.xml` et `/llms.txt` vers l'API de dev (`:8000`, ou `VITE_API_PROXY`). Le guide et la documentation sont servis depuis `public/guide/` et `public/documentation/` sur http://localhost:5180/guide/ et http://localhost:5180/documentation/.
