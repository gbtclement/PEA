# SEO et mise en ligne

L'application tourne en local, mais elle est prête à être indexée le jour où elle sera publiée.

## Ce qui est en place

- **Métadonnées par page** (`frontend/src/seo/usePageMeta.ts`) : titre, description, adresse canonique, Open Graph, Twitter Cards.
- **schema.org en JSON-LD** (`frontend/src/seo/schema.ts`) :
  - `WebApplication` pour l'accueil ;
  - `Corporation` avec `tickerSymbol` pour une action ;
  - `InvestmentFund` pour un ETF ;
  - `BreadcrumbList`.
- **Structure sémantique** : `header`, `nav`, `main`, `footer`, un seul `h1` par page.
- **Fichiers générés par l'API** (`backend/app/api/routes/seo.py`) : `/robots.txt`, `/sitemap.xml`, `/llms.txt`.
- **Page 404** en `noindex` pour les adresses inconnues.

## HTML préparé par l'API

Les pages publiques (`/`, `/explorer`, `/etf`, `/titres/<id>`, `/premium`, pages légales) ne sont plus une coquille vide :

1. nginx envoie la demande à `GET /api/seo/page?path=…` ;
2. l'API lit le `index.html` construit par Vite dans le conteneur web (`/_spa/index.html`, gardé une minute) et le remplit (`backend/app/services/seo/`) :
   - **en-tête** : titre, description, canonique, Open Graph, JSON-LD, mêmes textes que `usePageMeta` ;
   - **résumé lisible** dans `#root` (nom, cours, score et ses raisons, top 10, liste) : un robot ou un visiteur le voit avant le JavaScript ;
   - **données embarquées** (`<script id="cotalyx-data">`) sous les mêmes clés que TanStack Query : la page s'affiche sans redemander l'API (`seedFromPage`, `lib/queryClient.ts`) ;
   - **préchargement** (`modulepreload`) du code de la page, lu dans le manifeste de Vite (`/_spa/manifest.json`) ;
3. le navigateur peint ce résumé, puis React démarre et le remplace (`lib/boot.ts`).

Les données embarquées sont calculées **pour le demandeur** (favoris, enveloppes) : la page répond toujours `private, no-cache`. Un titre inconnu répond `404` en `noindex`.

!> Si l'API ne répond pas, nginx sert le `index.html` statique : l'application fonctionne comme avant, sans le résumé.

## Plan du site

`/sitemap.xml` est un **index** qui renvoie vers :

| Fichier | Contenu |
|---|---|
| `/sitemap-pages.xml` | Pages fixes publiques |
| `/sitemap-actions-1.xml`, `-2`… | Fiches d'actions, 10 000 au plus par fichier |
| `/sitemap-etf-1.xml`… | Fiches d'ETF |
| `/sitemap-guide.xml` | Accueil du guide |

Seuls les titres actifs **qui ont un cours** y figurent (les autres sont cachés des listes). `lastmod` est la date du dernier cours ou du dernier score. Le guide navigue par `#/…` : les moteurs n'en voient que l'accueil.

## Performances

- **JavaScript** : routes chargées à la demande, graphiques ECharts chargés quand ils deviennent visibles. Budget de 150 Ko compressés pour l'accueil : `npm run check:bundle`.
- **Explorer paginé côté serveur** : 50 lignes par page, la suite se charge en défilant.
- **Cache** : réponses publiques de l'API mises en cache avec empreinte (voir [API](api.md#cache-http)) ; fichiers `/assets/` gardés un an ; `index.html` et pages HTML toujours revalidés.
- **Mesure** : `npm run lighthouse` (application lancée sur `:8095`) note l'accueil, l'Explorer et une fiche en mode téléphone. Objectif : 95 dans chaque catégorie ; le SEO n'atteint 100 qu'avec `SEO_INDEXING=true`.

## Pages jamais indexées

Portefeuille, Assistant IA, Réglages et **Prévisions** sont toujours en `noindex` et absentes du sitemap. Les prévisions le sont par prudence réglementaire (AMF).

## Réglages

| Variable `.env` | Local (défaut) | En ligne |
|---|---|---|
| `SEO_INDEXING` | `false` : robots.txt interdit tout | `true` : seules les pages publiques (accueil, Explorer, ETF, fiches) sont autorisées |
| `PUBLIC_BASE_URL` | `http://localhost:8095` | L'adresse publique, utilisée dans le sitemap, robots.txt et llms.txt |

!> Même avec `SEO_INDEXING=true`, l'API publique doit rester lisible par les robots : React complète les pages à partir de l'API.

## À prévoir avant une mise en ligne

- **Comptes** : les pages personnelles demandent déjà une connexion ([Comptes utilisateurs](comptes.md)). Il restera à passer `COOKIE_SECURE=true`, à brancher le SMTP de Brevo et à remplacer les textes provisoires des CGU, de la politique de confidentialité et des mentions légales.
- **Protéger `/documentation/`** (authentification nginx, ou accès réservé aux administrateurs) : elle décrit le fonctionnement interne et n'a aujourd'hui aucune protection.
- **HTTPS** et un nom de domaine devant nginx.
- **Vraie IP des visiteurs** : si le HTTPS est assuré par un proxy placé devant nginx (Caddy, Traefik, Cloudflare, hébergeur), nginx ne voit plus que l'IP de ce proxy, et les limites par IP deviennent communes à tout le site : 5 inscriptions par heure pour tout le monde, blocage général après 30 mots de passe faux. Dans `frontend/nginx/default.conf.template`, ajouter `set_real_ip_from <IP ou réseau du proxy>;` et `real_ip_header X-Forwarded-For;` (ou `CF-Connecting-IP` derrière Cloudflare). Voir [Comptes](comptes.md#limites-anti-abus).
- Une fois le HTTPS en place : **`HSTS_ENABLED=true`** dans `.env`. Les navigateurs refuseront ensuite le HTTP pendant un an : ne l'activez pas avant que le certificat soit stable.
- **Turnstile** : ajouter le domaine public au widget Cloudflare et renseigner `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET_KEY`.
- **Google** : déclarer `https://<domaine>/api/auth/google/callback` dans les URI de redirection du client OAuth, et publier l'écran de consentement (sinon seuls les comptes de test peuvent se connecter).
- Régénérer la clé SMTP Brevo et le secret du client Google s'ils ont circulé ailleurs que dans `.env`.
- Vérifier le cadre **AMF** si des recommandations sont affichées au grand public.
