# PEA Radar

Application personnelle pour repérer des actions éligibles au PEA et suivre son portefeuille.
Outil d'aide à la décision et d'apprentissage — pas un conseil en investissement.

## Lancer l'application

```bash
cp .env.example .env        # la première fois, puis remplacer APP_SECRET par une longue chaîne aléatoire
                            # et mettre votre adresse dans ADMIN_EMAIL
docker compose up -d --build
```

Dans `.env`, en local : `ADMIN_EMAIL=<votre adresse>`, `COOKIE_SECURE=false` et le SMTP de Mailpit (`SMTP_HOST=mailpit`, `SMTP_PORT=1025`, `SMTP_TLS=none`), déjà proposés par `.env.example`. En ligne : `COOKIE_SECURE=true`, les identifiants SMTP de Brevo, `HSTS_ENABLED=true` une fois le HTTPS en place, et les clés Turnstile. Facultatif partout : `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` pour le bouton « Continuer avec Google » (création du client OAuth et des clés Turnstile : documentation admin, page Installation).

**Premier démarrage** : le compte `ADMIN_EMAIL` devient administrateur et reçoit un mail pour choisir son mot de passe. En local, tous les mails arrivent dans **Mailpit** : http://localhost:8025. Les autres personnes créent leur compte avec « Créer un compte » (code à 6 chiffres reçu par mail).

> Vous aviez déjà l'application avant les comptes ? La mise à jour change les identifiants des utilisateurs de façon irréversible : sauvegardez d'abord la base (`docker compose exec -T db pg_dump -U pea pea_radar > ../pea-sauvegarde.sql`). Vos données sont reprises par le compte `ADMIN_EMAIL`.

Puis ouvrir http://localhost:8095. Le guide utilisateur (l'application et la bourse expliquées) est sur
http://localhost:8095/guide/, accessible depuis la barre latérale ; la documentation admin (technique, non liée dans la navigation) est sur http://localhost:8095/documentation/. Au premier démarrage, le worker télécharge la liste des
titres puis 5 ans d'historique : comptez une dizaine de minutes avant que tout soit rempli,
et environ une heure pour les données fondamentales.

## Développement

```bash
# Backend (code monté en volume, rechargement automatique, API sur http://localhost:8000)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db api worker
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest

# Frontend (http://localhost:5180, proxy /api vers le port 8000)
cd frontend && npm install && npm run dev
npm test
npm run gen:api   # régénère les types TypeScript depuis l'API
```

## Fonctionnalités

- **Comptes** : inscription avec code de validation par mail, connexion (« Rester connecté »), mot de passe oublié, alerte « nouvelle connexion » avec bouton « Ce n'était pas moi », « Continuer avec Google », case anti-robot Cloudflare Turnstile, blocage 15 min après 10 mots de passe faux, refus des mots de passe connus dans les fuites (Have I Been Pwned, sans jamais envoyer le mot de passe), en-têtes de sécurité nginx (CSP, HSTS en option). Sans compte, l'accueil, l'Explorer, les ETF et les fiches restent consultables ; prévisions, portefeuille, favoris, assistant et réglages demandent une connexion.
- **Accueil** : top 10 du score mixte, indices, compteur d'ordres de l'année, plus fortes hausses/baisses, carte du marché.
- **Explorer / ETF** : tous les titres, filtres (secteur, pays, place, score, prix, liquidité, favoris) et tris, conservés dans l'URL.
- **Prévisions** : prédictions à 1 jour, 1 semaine et 1 mois calculées sans API à partir de 14 signaux techniques (cassures, tendances, RSI, MACD…), triables ; statistiques historiques de chaque signal sur 5 ans (cas, % de hausses, gain moyen, après frais, comparaison au CAC 40) ; bulletin de notes : test honnête sur l'année écoulée (statistiques recalculées sans elle) puis suivi réel des prédictions de chaque matin. Des estimations, pas des certitudes.
- **Fiche d'un titre** : graphique TradingView (bougies, volume, moyennes 50/200 jours, RSI, MACD), score détaillé, fondamentaux, simulateur « et si j'avais investi », frais estimés, prévisions court terme, actualités, bouton « + J'ai acheté ».
- **Portefeuille** : saisie manuelle des ordres (frais calculés selon votre grille, modifiables), positions avec PRU frais inclus, plus/moins-values latentes et réalisées, répartition par titre et par secteur, évolution de la valeur, compteur X/12 ordres avec alerte de rythme. Une vente supérieure à la quantité détenue est refusée.
- **Assistant IA** (Claude) : page dédiée avec l'historique des conversations et leur coût estimé, et panneau latéral ouvert par les boutons ✨ (top 10, fiche d'un titre) avec des questions prêtes. Claude consulte les données de l'application (recherche, fiche, historique et indicateurs, top 10, portefeuille, simulation d'achat passé) et l'actualité sur le web ; réponses en direct, mot par mot.
- **Réglages** : clé API Claude (chiffrée en base avec `APP_SECRET`, jamais renvoyée au navigateur ; ou variable `ANTHROPIC_API_KEY`) et modèle IA (Claude Opus 5 par défaut) ; ordres minimum par an, frais en cas de non-respect, grille de courtage de votre caisse régionale ; pour l'administrateur, corrections manuelles de l'éligibilité PEA.

Le score est recalculé toutes les 5 minutes pendant la séance. Il sert à trier et à comprendre, pas à prédire.

## Référencement (SEO)

L'application est prête à être indexée le jour où elle sera mise en ligne :

- chaque page a son titre, sa description, son adresse canonique, ses balises Open Graph/Twitter et ses données schema.org (`WebApplication`, `Corporation`, `InvestmentFund`, `BreadcrumbList`) ;
- `/robots.txt`, `/sitemap.xml` et `/llms.txt` sont générés par l'API ;
- le portefeuille, l'assistant, les réglages, les prévisions et les écrans de code ou de mot de passe sont toujours en `noindex` ; `/connexion` et `/inscription` sont indexables.

Deux variables dans `.env` :

| Variable | Local (défaut) | En ligne |
|---|---|---|
| `SEO_INDEXING` | `false` : robots.txt interdit tout | `true` : seules les pages publiques (accueil, explorateur, ETF, fiches) sont autorisées |
| `PUBLIC_BASE_URL` | `http://localhost:8095` | l'adresse publique, utilisée dans le sitemap, robots.txt et llms.txt |

À la mise en ligne, prévoir aussi une pré-génération (prerendering) des pages publiques : les moteurs indexent plus sûrement du HTML déjà rempli qu'une application React.

## Tests de bout en bout

```bash
cd frontend && npx playwright install chromium   # une fois
npm run e2e                                        # l'application doit tourner sur http://localhost:8095 (parcours, inscription via Mailpit, mise en page, SEO, en-têtes de sécurité)
# si .env vise Brevo, envoyer d'abord les mails vers Mailpit :
# docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --wait api worker && docker compose restart web
```

Guide et documentation admin (Docsify) : `frontend/public/guide/` et `frontend/public/documentation/`, servis sur `/guide/` et `/documentation/`. Documentation de conception : `docs/superpowers/specs/`. Contexte pour Claude Code (architecture, commandes, conventions, points d'attention) : `CLAUDE.md`.
