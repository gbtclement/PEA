# Cotalyx : mobile, SEO et performances, préparation de la mise en ligne

Date : 2026-10-03. Complète `2026-10-01-cotalyx-design.md` (blocs A à D, fusionnés). Le spec d'origine (`2026-09-26-pea-radar-design.md`) reste la référence pour tout ce qui n'est pas modifié ici.

## Objectif

Rendre Cotalyx prête pour le grand public :

- **utilisable de bout en bout sur un téléphone** (360 px de large), sauf l'onglet Admin ;
- **très bien référencée et rapide** : contenu public lisible par les moteurs sans JavaScript, score Lighthouse mobile ≥ 95 (Performance, SEO, Accessibilité, Bonnes pratiques) sur les pages publiques ;
- **prête à installer sur un serveur** : HTTPS, sauvegardes, surveillance, guide de mise en ligne. L'hébergeur n'est pas encore choisi : tout reste générique (Docker Compose sur une machine Linux).

Avertissement « outil d'aide à la décision, pas un conseil en investissement » : inchangé, toujours présent, y compris sur mobile.

## Constat de départ (2026-10-03)

- Mise en page : `min-w-[1024px]` sur le layout, barre latérale fixe de 240 px, pages pensées pour 1100–1440 px.
- Rendu : SPA React rendue dans le navigateur ; `index.html` ne contient ni titre de page, ni description, ni contenu. Titre, description, canonical et JSON-LD sont posés par `usePageMeta` après le chargement du JavaScript. `sitemap.xml`, `robots.txt` et `llms.txt` sont servis par l'API.
- Poids : bundle principal 417 Ko (126 Ko gzip) ; ECharts 573 Ko (195 Ko gzip), chargé dès l'accueil (carte du marché).
- Explorer et ETF : `GET /api/screener` renvoie toute une région d'un coup (Europe actions : 2,9 Mo, ~1 s ; ~3,5 Mo et ~5 Mo pour les États-Unis une fois tous les cours chargés) ; tri, filtres et recherche côté navigateur.
- Exploitation : Docker Compose local, ports de l'API (8000), de la base et de Mailpit exposés ; ni HTTPS, ni sauvegarde, ni surveillance.

## Découpage

Une branche par bloc, PR à la fin de chaque bloc, arrêt après chaque bloc (l'utilisateur fait `/compact`).

| Bloc | Branche | Contenu |
|---|---|---|
| E | `mobile` | mise en page responsive, navigation mobile, listes en cartes, fenêtres plein écran |
| F | `seo-performances` | HTML enrichi par l'API, données embarquées, Explorer paginé côté serveur, découpage du JavaScript, cache, sitemap découpé, contrôle Lighthouse |
| G | `mise-en-ligne` | Compose de production, HTTPS (Caddy), sauvegardes, surveillance et alertes, guide de mise en ligne |

L'ordre compte : E avant F (Google indexe la version mobile ; les mesures de F se font sur la mise en page mobile), F avant G (la configuration de production intègre les en-têtes de cache et le rendu enrichi).

---

## Bloc E — Mobile

### E1. Points de rupture

- Téléphone : < 768 px ; tablette : 768–1023 px ; ordinateur : ≥ 1024 px (inchangé).
- Suppression de `min-w-[1024px]`. Plus aucune page ne défile horizontalement à 360 px.
- Une colonne sous 768 px, marges latérales de 16 px ; les grilles à deux colonnes (`xl`) s'empilent.

### E2. Navigation

- Sous 1024 px : la barre latérale disparaît, remplacée par une **barre du haut** (logo, bouton menu ☰, menu du compte). Le menu s'ouvre en **tiroir à gauche** (mêmes liens que la barre latérale, état des places, lien du guide, bouton de connexion ou menu du compte) ; il se ferme au choix d'un lien, à la touche Échap, au toucher hors du tiroir.
- À partir de 1024 px : barre latérale actuelle, inchangée.
- Le bandeau d'inscription et le pied de page (avertissement, liens légaux) restent visibles sur mobile.

### E3. Listes (Explorer, ETF, Prévisions)

- Sous 768 px, chaque ligne devient une **carte** : nom, symbole et place, cours avec sa devise, variation du jour, score, badges d'enveloppe, favori. Toucher la carte ouvre la fiche.
- Tri et filtres dans un panneau **« Filtres »** plein écran (mêmes filtres qu'aujourd'hui, toujours conservés dans l'URL) ; le choix de région reste visible au-dessus de la liste.
- La liste reste virtualisée (fluide avec des milliers de lignes).

### E4. Fiche d'un titre

- Graphique en pleine largeur, hauteur adaptée à l'écran ; boutons de période dans une rangée qui défile horizontalement ; cases des indicateurs repliées dans un menu.
- Cartes empilées dans l'ordre : cours, graphique, score, fondamentaux, simulateur, prévisions, actualités.
- Actions (favori, alerte, ordre, assistant) dans une **barre fixe en bas de l'écran** sur téléphone.

### E5. Autres pages

- Accueil : top 10, hausses et baisses, carte du marché et indices empilés ; la carte du marché garde une hauteur lisible.
- Portefeuille, Réglages, Premium, compte (connexion, inscription, mot de passe…), pages légales, guide : formulaires et tableaux empilés ; les tableaux larges (positions, historique des ordres) deviennent des cartes.
- Fenêtres (ordre, alerte, modification) : **plein écran** sur téléphone.
- Assistant : conversation en plein écran ; zone de saisie fixée en bas, qui reste visible au-dessus du clavier.
- Onglet Admin : non adapté (reste utilisable en défilant), hors périmètre.

### E6. Tactile et accessibilité

- Zones cliquables d'au moins 44 × 44 px ; aucune information disponible seulement au survol (les infobulles s'ouvrent aussi au toucher).
- Champs de saisie en 16 px minimum (pas de zoom automatique d'iOS).
- Les états actifs restent visibles au clavier sur ordinateur.

### E7. Tests

- Vitest : ouverture et fermeture du tiroir, cartes de liste, barre d'actions de la fiche.
- Playwright à 390 px et 360 px sur toutes les pages hors Admin : pas de défilement horizontal, aucune carte coupée, menu utilisable, un seul `h1`.
- Le test existant 1100–1440 px (`layout.spec.ts`) reste.

---

## Bloc F — SEO et performances

### F1. HTML enrichi par l'API

- Pour les pages publiques — accueil, Explorer, ETF, fiche de titre (`/titres/:id`), Premium, CGU, CGV, mentions légales, confidentialité — nginx demande à l'API une version de `index.html` (route dédiée, par ex. `GET /api/seo/page?path=…`), au lieu du fichier statique. Les autres pages (privées) gardent `index.html` statique.
- Le HTML renvoyé contient :
  - `<title>`, `<meta name="description">`, `<link rel="canonical">`, balises Open Graph et Twitter, `robots` (`noindex` pour les pages privées, comme aujourd'hui) ;
  - le JSON-LD de la page (fil d'Ariane ; pour une fiche, le titre financier avec cours, devise et date) ;
  - un **résumé du contenu en HTML sémantique** dans le conteneur de l'application (fiche : nom, cours et devise, variation, score et ses raisons, secteur, place, enveloppes ; accueil : top 10 ; Explorer et ETF : premiers titres et liens vers les fiches). React remplace ce contenu au démarrage ;
  - les **données de la page embarquées** (JSON dans une balise `<script type="application/json">`), reprises par le cache des requêtes : la page s'affiche sans aller-retour vers l'API.
- Les textes générés côté serveur sont les mêmes que côté navigateur (même source pour titre et description ; un test le vérifie).
- Si l'API ne répond pas, nginx sert `index.html` statique (l'application fonctionne comme aujourd'hui).
- Une fiche inconnue renvoie un vrai code 404 avec une page « titre introuvable » en `noindex`.

### F2. Explorer et ETF paginés côté serveur

- `GET /api/screener` accepte tri, ordre, filtres (ceux de l'interface actuelle), recherche texte, région, type, `limit` (50 par défaut) et `offset` ; il renvoie `{items, total}`.
- L'interface charge la première page, puis les suivantes au défilement (défilement infini), en gardant la virtualisation ; le compteur affiche `total`.
- Les filtres restent dans l'URL (liens partageables inchangés).
- Objectif : première page ≤ 60 Ko compressé, affichée en moins de 300 ms côté serveur.
- Les listes de valeurs des filtres (secteurs, pays, places) viennent d'une petite route dédiée (`GET /api/screener/facets?region=…&kind=…`).

### F3. JavaScript, images, polices

- ECharts chargé seulement quand la carte du marché devient visible (import dynamique + observation de la visibilité) ; Lightweight Charts seulement sur la fiche.
- Bibliothèques séparées en morceaux stables (React, TanStack, UI) pour profiter du cache.
- Objectif : premier affichage de l'accueil sur mobile ≤ 120 Ko de JavaScript compressé.
- Images (icône, logo, image de partage Open Graph 1200×630) aux bons formats et dimensions ; police servie localement avec `font-display: swap` et préchargement ; dimensions réservées pour éviter tout décalage de mise en page (CLS ≈ 0).

### F4. Cache

- Fichiers versionnés (`/assets/*`) : `Cache-Control: public, max-age=31536000, immutable` ; `index.html` et HTML enrichi : `no-cache`.
- Réponses publiques de l'API (top 10, hausses et baisses, carte du marché, listes, fiche, historique) : `Cache-Control: public, max-age=30` à `60` et `ETag` ; jamais pour une réponse qui dépend du compte (favoris, enveloppes d'un membre) — celles-ci gardent `private, no-store`.
- Compression gzip (déjà active) et Brotli si disponible dans nginx.

### F5. Sitemap et robots

- Index de sitemaps (`/sitemap.xml`) pointant vers des fichiers d'au plus 10 000 adresses : pages fixes, fiches d'actions, fiches d'ETF, pages du guide.
- `lastmod` de chaque fiche = date du dernier cours ou du dernier score.
- Seules les fiches qui ont un cours figurent dans le sitemap (les titres cachés des listes ne sont pas proposés aux moteurs).
- `robots.txt` et `llms.txt` inchangés dans leur principe, mis à jour si des chemins changent.

### F6. Contrôle

- Lighthouse en mode mobile, automatisé (Lighthouse CI ou script Playwright + `lighthouse`), sur l'accueil, l'Explorer et une fiche : seuil 95 dans les quatre catégories ; le rapport est joint à la PR.
- Tests backend : le HTML enrichi contient titre, description, canonical, JSON-LD et résumé ; 404 pour une fiche inconnue ; pas de données de compte dans une réponse mise en cache.
- Tests e2e : la page servie sans JavaScript contient déjà le contenu principal ; l'Explorer charge la page suivante au défilement.

---

## Bloc G — Préparation de la mise en ligne

### G1. Compose de production

- `docker-compose.prod.yml` (utilisé avec le fichier de base) : aucun port exposé hormis 80 et 443 (proxy) ; pas de Mailpit (SMTP réel) ; `restart: unless-stopped` ; limites de mémoire par service ; journaux Docker tournants (taille et nombre de fichiers limités).
- `.env.production.example` : toutes les variables nécessaires en ligne (`PUBLIC_BASE_URL`, `SEO_INDEXING=true`, `COOKIE_SECURE=true`, `HSTS_ENABLED=true`, SMTP, Stripe, sauvegardes, surveillance), sans aucune valeur secrète.

### G2. HTTPS

- Service **Caddy** devant nginx : certificat Let's Encrypt obtenu et renouvelé automatiquement pour le domaine de `PUBLIC_BASE_URL`, redirection HTTP → HTTPS.
- nginx fait confiance à l'adresse IP transmise par Caddy (`set_real_ip_from` sur le réseau Docker, `real_ip_header X-Forwarded-For`) : les limites anti-abus par IP visent le vrai visiteur.
- `HSTS_ENABLED=true` en production.

### G3. Sauvegardes

- Service de sauvegarde : chaque nuit, `pg_dump` compressé de la base ; conservation de 7 sauvegardes quotidiennes et 4 hebdomadaires sur le serveur.
- Copie optionnelle vers un stockage compatible S3 si les identifiants sont présents dans `.env` (Backblaze B2, Scaleway, OVH…).
- Commande de restauration documentée ; un test restaure une sauvegarde dans une base de test.
- La sauvegarde de la nuit apparaît dans le suivi des tâches (`data_status`) : réussite, taille, erreur éventuelle.

### G4. Surveillance et alertes

- `GET /api/health/details`, protégé par un jeton (`HEALTH_TOKEN`), en plus du `/api/health` public actuel : état de la base, âge de la dernière réussite des tâches essentielles (cours, historique, univers, sauvegarde), place disque libre, retard des cours en séance ; code 503 si un seuil est dépassé.
- Un service externe gratuit (UptimeRobot ou équivalent) interroge cette adresse toutes les 5 minutes et prévient l'utilisateur par mail (réglage décrit dans le guide, fait par l'utilisateur).
- Le worker envoie un mail d'alerte à `ADMIN_EMAIL` quand une tâche essentielle échoue trois fois de suite ou n'a pas réussi depuis trop longtemps (au plus un mail par tâche et par jour), et un mail quand elle repart.

### G5. Guide de mise en ligne

Page « Mettre en ligne » de la documentation admin, pas à pas, sans supposer d'hébergeur : caractéristiques du serveur conseillé (4 Go de RAM, 80 Go de disque, Linux), installation de Docker, pointage du domaine (enregistrements DNS), copie du projet, remplissage du `.env`, premier lancement (et durée du premier chargement), vérifications (HTTPS, robots, sitemap, mail de test, paiement en mode test), réglage de la surveillance externe, restauration d'une sauvegarde, mise à jour de l'application.

### G6. Tests

- Sauvegarde puis restauration sur une base de test.
- `/api/health/details` : 401 sans jeton, 200 quand tout va bien, 503 quand une tâche essentielle est trop ancienne.
- Alerte du worker : envoyée après trois échecs, une seule fois par jour, mail de retour à la normale.

---

## Hors périmètre

- Choix et souscription de l'hébergeur, achat du domaine, réglage du service de surveillance externe (faits par l'utilisateur, guidés par G5).
- Onglet Admin et documentation admin sur mobile.
- Application mobile installable (PWA, mode hors ligne).
- Rendu serveur complet de l'application (SSR React).
