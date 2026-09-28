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
- Vérifier le cadre **AMF** si des recommandations sont affichées au grand public.
