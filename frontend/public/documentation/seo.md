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

## Pages jamais indexées

Portefeuille, Assistant IA, Réglages et **Prévisions** sont toujours en `noindex` et absentes du sitemap. Les prévisions le sont par prudence réglementaire (AMF).

## Réglages

| Variable `.env` | Local (défaut) | En ligne |
|---|---|---|
| `SEO_INDEXING` | `false` : robots.txt interdit tout | `true` : seules les pages publiques (accueil, Explorer, ETF, fiches) sont autorisées |
| `PUBLIC_BASE_URL` | `http://localhost:8095` | L'adresse publique, utilisée dans le sitemap, robots.txt et llms.txt |

!> Même avec `SEO_INDEXING=true`, l'API publique doit rester lisible par les robots : les pages sont remplies par le navigateur à partir de l'API.

## À prévoir avant une mise en ligne

- **Pré-génération** (prerendering) des pages publiques : les moteurs indexent plus sûrement du HTML déjà rempli qu'une application React.
- **Comptes** : les pages personnelles demandent déjà une connexion ([Comptes utilisateurs](comptes.md)). Il restera à passer `COOKIE_SECURE=true`, à brancher le SMTP de Brevo et à remplacer les textes provisoires des CGU, de la politique de confidentialité et des mentions légales.
- **Protéger `/documentation/`** (authentification nginx, ou accès réservé aux administrateurs) : elle décrit le fonctionnement interne et n'a aujourd'hui aucune protection.
- **HTTPS** et un nom de domaine devant nginx.
- **Vraie IP des visiteurs** : si le HTTPS est assuré par un proxy placé devant nginx (Caddy, Traefik, Cloudflare, hébergeur), nginx ne voit plus que l'IP de ce proxy, et les limites par IP deviennent communes à tout le site : 5 inscriptions par heure pour tout le monde, blocage général après 30 mots de passe faux. Dans `frontend/nginx/default.conf.template`, ajouter `set_real_ip_from <IP ou réseau du proxy>;` et `real_ip_header X-Forwarded-For;` (ou `CF-Connecting-IP` derrière Cloudflare). Voir [Comptes](comptes.md#limites-anti-abus).
- Une fois le HTTPS en place : **`HSTS_ENABLED=true`** dans `.env`. Les navigateurs refuseront ensuite le HTTP pendant un an : ne l'activez pas avant que le certificat soit stable.
- **Turnstile** : ajouter le domaine public au widget Cloudflare et renseigner `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET_KEY`.
- **Google** : déclarer `https://<domaine>/api/auth/google/callback` dans les URI de redirection du client OAuth, et publier l'écran de consentement (sinon seuls les comptes de test peuvent se connecter).
- Régénérer la clé SMTP Brevo et le secret du client Google s'ils ont circulé ailleurs que dans `.env`.
- Vérifier le cadre **AMF** si des recommandations sont affichées au grand public.
