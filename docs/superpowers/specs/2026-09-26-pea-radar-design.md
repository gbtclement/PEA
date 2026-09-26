# PEA Radar — Spécification de conception

- **Date :** 2026-09-26
- **Statut :** validée
- **Auteur :** Clément (besoin) · Claude (conception)

---

## 1. Objectif

Application web personnelle, exécutée en local via Docker, pour **aider à choisir quelles actions acheter** sur un PEA Crédit Agricole (formule **Invest Store Intégral**) et **suivre son portefeuille**.

### Ce que l'utilisateur a demandé
- Trouver quoi acheter : un **top 10** des actions intéressantes en page d'accueil, un explorateur complet (recherche, tri par variations en %), des fiches détaillées avec de **beaux graphiques**.
- Suivre son portefeuille par **saisie manuelle** des ordres (pas d'API Crédit Agricole ; import CSV reporté).
- Respecter la contrainte de la formule : **≥ 12 ordres/an** sinon ~96 €/an de frais (valeurs variables selon la caisse régionale).
- Un **assistant IA** (Claude) intégré pour analyser actions, top 10 et portefeuille.
- Données issues d'**API gratuites** (Yahoo Finance), avec quelques minutes de retard acceptables.
- Interface **React fluide**, thème **clair**, navigation **à gauche**, sobre mais soignée, **PC uniquement** (≥ 1280 px, optimisé 1400 px+).
- Architecture **propre et évolutive** : comptes utilisateurs et mise en ligne possibles plus tard.
- **SEO** complet (Hn, robots.txt, sitemap, schema.org, llms.txt) — en dernière étape.

### Critères de succès
1. `docker compose up` lance l'application complète sur `http://localhost:8080`.
2. La page d'accueil affiche un top 10 à jour (≤ 5 min de décalage en séance) avec l'explication de chaque score.
3. On trouve n'importe quelle action éligible PEA en moins de 3 clics et on voit son graphique en chandeliers.
4. Le portefeuille affiche positions, plus/moins-values et le compteur X/12 ordres.
5. L'assistant IA répond en s'appuyant sur les données réelles de l'application.

### Hors périmètre (pour l'instant)
Import CSV, comptes/inscription, mobile, données temps réel à la seconde, passage d'ordres, notifications, mise en ligne.

### Avertissement
L'application est un **outil d'aide à la décision et d'apprentissage**, pas un conseil en investissement. Un bandeau discret le rappelle en pied de page et dans l'assistant IA.

---

## 2. Architecture

### 2.1 Vue d'ensemble

```
Navigateur ──► web (nginx : SPA React + proxy /api) ──► api (FastAPI) ──► db (PostgreSQL)
                                                          ▲                 ▲
                                          Claude API ◄────┘                 │
                                                                 worker (tâches planifiées)
                                                                    │
                                                    Yahoo Finance / Euronext
```

4 conteneurs Docker Compose :

| Service | Rôle | Techno |
|---|---|---|
| `web` | Sert l'interface compilée, redirige `/api/*` vers `api` | nginx + build Vite |
| `api` | API REST + flux SSE du chat IA. **Ne contacte jamais Yahoo pendant une requête**, sauf pour l'intraday à la demande (mis en cache 60 s) | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| `worker` | Rafraîchissement des données, calcul des scores, mise à jour de l'univers | Python 3.12, APScheduler, même code que `api` |
| `db` | Stockage persistant (volume Docker) | PostgreSQL 16 |

`api` et `worker` partagent le même paquet Python (`backend/app`) mais sont des processus séparés : on peut faire évoluer ou multiplier l'un sans toucher à l'autre.

Un fichier `docker-compose.dev.yml` active le rechargement à chaud (Vite dev server + uvicorn `--reload`) pour le développement.

### 2.2 Arborescence

```
pea-radar/
├── docker-compose.yml / docker-compose.dev.yml / .env.example
├── backend/
│   ├── app/
│   │   ├── api/routes/        # un fichier par domaine (securities, rankings, portfolio, assistant, settings, meta)
│   │   ├── core/              # config, base de données, sécurité, utilisateur courant
│   │   ├── models/            # tables SQLAlchemy
│   │   ├── schemas/           # modèles Pydantic d'entrée/sortie
│   │   ├── repositories/      # accès base de données
│   │   ├── services/          # logique métier : scoring/, eligibility/, portfolio/, fees/, assistant/
│   │   ├── providers/         # sources externes derrière une interface commune : yahoo.py, euronext.py
│   │   ├── jobs/              # tâches du worker
│   │   └── seeds/             # listes de départ (indices hors Euronext, ETF PEA, calendrier boursier)
│   ├── alembic/               # migrations
│   └── tests/
├── frontend/
│   └── src/
│       ├── app/               # routeur, layout (barre latérale), providers
│       ├── features/          # home, explorer, etf, security, portfolio, assistant, settings
│       ├── components/ui/     # composants shadcn/ui
│       ├── components/charts/ # enveloppes Lightweight Charts et ECharts
│       ├── lib/api/           # client HTTP + types générés depuis l'OpenAPI du backend
│       └── seo/               # gestion des métadonnées par page (lot 5)
└── docs/
```

Règles de dépendance : `routes → services → repositories/providers`. Les services ne connaissent ni HTTP ni Yahoo directement. Les calculs (indicateurs, score, frais, positions) sont des **fonctions pures** testables sans base ni réseau.

### 2.3 Préparation multi-utilisateur
- Table `users` dès le départ ; un utilisateur par défaut est créé au démarrage.
- Toutes les données personnelles (ordres, favoris, conversations, réglages) portent un `user_id`.
- Une dépendance FastAPI unique `get_current_user()` renvoie aujourd'hui l'utilisateur par défaut ; demain, elle vérifiera une session ou un jeton, sans modifier les routes.

### 2.4 Configuration
Variables d'environnement (`.env`) : connexion PostgreSQL, `APP_SECRET` (chiffrement de la clé API en base), fuseau `Europe/Paris`, `ANTHROPIC_API_KEY` optionnelle (sinon saisie dans les Réglages). Paramètres métier (pondérations du score, seuils, fréquences) dans `backend/app/core/settings.py`, surchargeables par variables d'environnement.

---

## 3. Données

### 3.1 Univers des titres éligibles PEA
Aucune liste officielle complète n'existe (Euronext ne publie que la liste PEA-PME). L'accès aux données Crédit Agricole est exclu (connexion bancaire, conditions d'utilisation). L'univers est donc **reconstruit** :

1. **Actions Euronext** : liste complète téléchargée depuis Euronext (Paris, Amsterdam, Bruxelles, Milan, Lisbonne, Dublin, Oslo). Un instantané est versionné dans `seeds/` comme secours si le téléchargement échoue.
2. **Grands indices hors Euronext** (liste de départ versionnée) : DAX 40 (`.DE`), IBEX 35 (`.MC`), membres de l'Euro Stoxx 50 manquants.
3. **Liste officielle PEA-PME** d'Euronext, fusionnée.
4. **ETF éligibles PEA** : liste de départ d'environ 30 ETF populaires (ISIN + ticker Yahoo).

**Règle d'éligibilité automatique :** préfixe ISIN appartenant à l'UE-27 ou à l'EEE (IS, LI, NO) → `eligible`. Sinon → `non_eligible`.
**Cas `a_verifier` :** sociétés foncières de type SIIC/REIT (secteur immobilier coté exonéré d'IS, exclu du PEA), ou données incomplètes.
**Correction manuelle** dans les Réglages → statut `override_eligible` / `override_non_eligible`, prioritaire sur la règle automatique.

**Correspondance ticker Yahoo :** suffixe par place (`.PA`, `.AS`, `.BR`, `.MI`, `.LS`, `.IR`, `.OL`, `.DE`, `.MC`).

### 3.2 Source des cours : fournisseur interchangeable
Interface `MarketDataProvider` : `get_quotes(tickers)`, `get_daily_history(ticker, start)`, `get_intraday(ticker, interval)`, `get_fundamentals(ticker)`, `get_news(ticker)`.
Implémentation v1 : `YahooProvider` (bibliothèque `yfinance`, requêtes groupées, limiteur de débit global, 3 tentatives avec attente progressive). Un second fournisseur (Twelve Data, Alpha Vantage) pourra être branché sans modifier les services.

### 3.3 Rafraîchissement (worker)
Heures de bourse : jours ouvrés 9h00–17h35 (Europe/Paris), hors jours fériés Euronext (calendrier dans `seeds/`).

| Niveau | Contenu | Fréquence en séance |
|---|---|---|
| T1 | Indices (CAC 40, SBF 120, Euro Stoxx 50), puis favoris, positions du portefeuille et top 10 dès que ces fonctions existent (lots 2 et 3) | 2 min |
| T2 | Les 150 titres les plus échangés (montant moyen sur 20 séances ; ≈ SBF 120 + Euro Stoxx 50, dont la composition n'est fournie par aucune source gratuite) | 5 min |
| T3 | Reste de l'univers | 30 min |
| Quotidien 07h00 | Mise à jour de l'univers et de l'éligibilité | 1×/jour |
| Quotidien 07h30 | Données fondamentales, historique journalier (clôture de la veille) | 1×/jour |
| Après chaque cycle T2 | Recalcul des scores et du classement | ~5 min |

Hors séance : aucune requête de cours ; derniers cours affichés avec leur horodatage.
Historique journalier conservé sur **5 ans**. L'intraday (barres de 5 min) est chargé à la demande pour le graphique « 1 jour », mis en cache 60 s.

### 3.4 Modèle de données (tables principales)
- `users` (id, nom, créé le)
- `securities` (id, isin, ticker_yahoo, nom, type `stock|etf|index`, place, pays, secteur, statut_eligibilite, source_eligibilite, indices[], actif)
- `quotes` (security_id, cours, variation_jour_pct, volume, horodatage) — dernier cours
- `daily_prices` (security_id, date, ouverture, haut, bas, clôture, volume)
- `fundamentals` (security_id, per, bpa, croissance_bpa, croissance_ca, dette_capitaux_propres, marge_nette, rendement_dividende, capitalisation, mis à jour le)
- `scores` (security_id, calculé le, total, technique, fondamental, détail JSON, liquide bool, données_incomplètes bool)
- `favorites` (user_id, security_id)
- `orders` (id, user_id, security_id, date, sens `achat|vente`, quantité, prix_unitaire, frais, note)
- `user_settings` (user_id, clé_api_chiffrée, modèle_ia, ordres_min_annuels, frais_non_respect, grille_frais JSON)
- `conversations` / `messages` (user_id, titre, contexte security_id optionnel, contenu, tokens entrée/sortie, coût estimé)
- `data_status` (dernière mise à jour réussie par tâche, dernière erreur)

---

## 4. Score mixte (sur 100)

### 4.1 Filtre préalable (entrée dans le top 10)
- Titre `eligible` ou `override_eligible`, type `stock`.
- **Liquidité :** montant moyen échangé sur 20 séances ≥ 500 000 € (paramétrable).
- Au moins 200 séances d'historique.

Les titres qui ne passent pas le filtre ont quand même un score (visible dans l'explorateur) mais ne figurent pas dans le top 10.

### 4.2 Partie technique — 50 points
| Composant | Pts | Règle |
|---|---|---|
| Tendance | 20 | cours > MM50 : +7 · cours > MM200 : +7 · MM50 > MM200 : +6 |
| Dynamique 3 mois | 15 | performance 3 mois moins celle du CAC 40 : linéaire de −10 pts de % → 0 à +10 pts de % → 15 (bornée) |
| RSI 14 | 10 | 40–60 → 10 · 30–40 ou 60–70 → 6 · < 30 → 4 · > 70 → 0 |
| MACD (12, 26, 9) | 5 | croisement haussier dans les 5 dernières séances → 5 · MACD > signal → 3 · sinon 0 |

### 4.3 Partie fondamentale — 50 points
| Composant | Pts | Règle |
|---|---|---|
| Valorisation | 15 | PER ≤ 0,8 × médiane du secteur → 15, linéaire jusqu'à 1,5 × médiane → 0 ; PER négatif ou absent → 0 |
| Croissance | 15 | croissance annuelle du BPA (7,5) et du chiffre d'affaires (7,5) : linéaire de 0 % → 0 à ≥ 15 % → 7,5 |
| Solidité | 10 | dette/capitaux propres : < 0,5 → 5, linéaire jusqu'à > 2 → 0 · marge nette : linéaire de 0 % → 0 à ≥ 10 % → 5 |
| Dividende | 10 | rendement 0 → 0, linéaire jusqu'à 2 % → 10 · 2–6 % → 10 · 6–8 % → 7 · > 8 % → 5 (rendement suspect) |

### 4.4 Règles complémentaires
- **Données manquantes :** un composant sans donnée est exclu ; le total est ramené sur 100 au prorata des points disponibles, et le score porte l'indicateur `données_incomplètes` (badge dans l'interface). Si plus de 40 % des points manquent, le titre est exclu du top 10.
- **ETF :** score **technique uniquement**, ramené sur 100 ; classement séparé (onglet ETF).
- **Départage :** à score égal, le plus liquide passe devant.
- **Explication :** chaque composant produit une phrase courte en français (ex. « ✅ Tendance haussière (cours au-dessus des moyennes 50 et 200 jours) +20 »), stockée dans `scores.détail`.
- Pondérations et seuils dans la configuration.

---

## 5. Écrans

### 5.1 Structure commune
- **Barre latérale gauche fixe (240 px)**, fond blanc : logo, Accueil, Explorer, ETF, Portefeuille, Assistant IA, Réglages. En bas : état du marché (🟢 ouvert / 🔴 fermé), heure de dernière mise à jour, bandeau si les données sont anciennes (source indisponible).
- **Contenu à droite**, fond gris très clair, cartes blanches.
- **Style :** thème clair ; police Inter (chiffres à chasse fixe `tabular-nums`) ; couleur principale bleu indigo ; vert pour la hausse, rouge pour la baisse ; coins arrondis, ombres légères, espacements généreux. Largeur minimale 1280 px, mise en page optimisée à partir de 1400 px.
- Les listes se rafraîchissent automatiquement toutes les 60 s pendant la séance (TanStack Query), sans recharger la page.

### 5.2 Accueil
- Bandeau des indices : CAC 40, SBF 120, Euro Stoxx 50 (valeur, variation, mini-courbe du jour).
- **Top 10** : rang, nom, cours, variation du jour, jauge de score, 3 principales raisons, mini-courbe 3 mois, bouton ✨ IA. Un clic ouvre la fiche.
- Carte **compteur d'ordres** (X/12, barre de progression, « il en reste N d'ici le 31/12 », alerte si en retard sur le rythme attendu `ordres_min × jours écoulés / 365`).
- Plus fortes hausses et baisses du jour (5 de chaque, univers liquide).
- **Carte du marché** (treemap ECharts) : titres liquides regroupés par secteur, taille = capitalisation, couleur = variation du jour.

### 5.3 Explorer
- Recherche par nom, ticker ou ISIN.
- Filtres : secteur, pays, place, score minimum, fourchette de prix, éligibilité, « liquides uniquement ».
- **Tableau triable et virtualisé** (TanStack Table + Virtual, fluide sur plus de 1 000 lignes) : ⭐, nom, ticker, cours, variations 1 j / 1 sem / 1 mois / 1 an, score, PER, rendement, mini-courbe.
- Filtres et tri conservés dans l'URL (lien partageable, retour arrière fiable).

### 5.4 ETF
Même composant que l'explorateur, limité aux ETF, score technique, colonnes adaptées (indice suivi, frais courants si disponibles).

### 5.5 Fiche d'une action
- **En-tête :** nom, ticker, place, cours, variation, badge d'éligibilité (Éligible / À vérifier / Non éligible), boutons ⭐, ✨ Demander à l'IA, « + J'ai acheté » (ouvre le formulaire d'ordre prérempli).
- **Graphique principal (Lightweight Charts) :** chandeliers + volume ; périodes 1J, 1S, 1M, 6M, 1A, 5A ; moyennes 50/200 activables ; panneaux RSI et MACD sous le graphique.
- **Cartes :** détail du score (barres par composant + phrases) · données fondamentales · simulateur « Si j'avais investi [montant] il y a [1 sem / 1 mois / 6 mois / 1 an] » (gain en € et %, frais inclus) · actualités récentes (titres et liens) · aide sur les frais (« Pour 400 € : ≈ 1,92 € (0,48 %). À partir de 500 € : 0,18 % »).

### 5.6 Portefeuille
- Chiffres clés : valeur totale, montant investi, plus/moins-value en € et en %, variation du jour.
- Compteur d'ordres de l'année (achats + ventes, année civile).
- Graphiques ECharts : répartition par titre et par secteur (anneaux) ; évolution de la valeur du portefeuille depuis le premier ordre (reconstituée à partir des ordres et des clôtures journalières).
- Tableau des positions : titre, quantité, **PRU** (prix de revient unitaire, frais inclus), cours, valeur, plus/moins-value.
- Historique des ordres (modifier / supprimer).
- **Formulaire d'ordre :** date, sens, titre (recherche), quantité, prix ; frais **calculés automatiquement** selon la grille des réglages et modifiables à la main. Une vente supérieure à la quantité détenue est refusée.

### 5.7 Assistant IA
- Page dédiée : conversations à gauche, chat à droite, coût estimé par conversation.
- **Panneau latéral** ouvert par tout bouton ✨, avec l'action concernée comme contexte et des questions prêtes : « Analyse cette action », « Pourquoi est-elle dans le top 10 ? », « Aurais-je dû l'acheter il y a une semaine ? », « Quels sont les risques ? ».
- Si aucune clé API n'est configurée : message explicatif et lien vers les Réglages.

### 5.8 Réglages
- Clé API Claude (saisie, statut « configurée » ; jamais réaffichée), modèle IA.
- Paramètres de la caisse régionale : ordres minimum par an (défaut 12), frais en cas de non-respect (défaut 96 €), grille de courtage (défaut Intégral : 0,48 % jusqu'à 500 €, 0,18 % de 500 à 1 000 €, 0,12 % au-delà ; le taux de la tranche s'applique au montant total de l'ordre).
- Corrections manuelles d'éligibilité.

---

## 6. Assistant IA — fonctionnement

- **Modèle par défaut :** `claude-opus-5` (modifiable dans les Réglages), réflexion adaptative, réponses en streaming. Mécanisme de repli côté serveur activé en cas de refus du modèle.
- **Flux :** le frontend envoie le message à `POST /api/assistant/conversations/{id}/messages` → l'API appelle Claude avec des **outils** → exécute les outils demandés sur ses propres données → renvoie la réponse en **SSE** (affichage mot par mot).
- **Outils exposés à Claude :**
  - `search_securities(query)`
  - `get_security_overview(ticker)` : cours, score détaillé, fondamentaux, éligibilité
  - `get_price_history(ticker, period)` : clôtures + indicateurs
  - `get_top10()`
  - `get_portfolio()` : positions, performance, compteur d'ordres
  - `simulate_past_investment(ticker, amount, date)`
  - recherche web (outil serveur Anthropic) pour l'actualité
- **Consigne système :** répondre en français, de façon pédagogique ; s'appuyer sur les données des outils en citant leur horodatage ; distinguer faits et opinions ; ne jamais présenter une prévision comme certaine ; rappeler qu'il ne s'agit pas d'un conseil en investissement réglementé.
- La clé API est stockée chiffrée en base (ou lue depuis l'environnement) et **n'est jamais envoyée au navigateur**.
- Tokens consommés et coût estimé enregistrés par message.

---

## 7. Gestion des erreurs
- **Fournisseur de données indisponible :** nouvelles tentatives avec attente progressive ; en cas d'échec, les dernières données restent servies, `data_status` enregistre l'erreur, l'interface affiche un bandeau « Données du JJ/MM HH:MM ».
- **Données partielles d'un titre :** score avec badge « données incomplètes », jamais d'erreur bloquante.
- **API :** erreurs JSON uniformes `{code, message}` ; validation Pydantic pour toutes les entrées.
- **Frontend :** gestion d'erreur par page (une section en échec n'empêche pas l'affichage du reste), notifications pour les actions (ordre enregistré, erreur).
- **IA :** messages clairs pour clé absente ou invalide, quota atteint, service indisponible ; une réponse interrompue reste affichée avec la mention « réponse interrompue ».

---

## 8. Performance
- Les pages ne lisent que la base (réponses API < 200 ms visées) ; les appels externes se font dans le worker.
- Index SQL sur `security_id`, `date`, `user_id`, `score total`.
- Découpage du code par page ; bibliothèques de graphiques chargées à la demande.
- Tableaux virtualisés ; mise en cache des requêtes côté client (TanStack Query).

---

## 9. Tests
- **Backend (pytest) :** fonctions pures testées en priorité (indicateurs MM/RSI/MACD, chaque composant du score, éligibilité par ISIN, grille de frais, calcul des positions/PRU, compteur d'ordres) ; routes testées sur une base PostgreSQL de test ; fournisseurs externes simulés (aucun appel réseau en test) ; outils de l'assistant testés sans appeler Claude.
- **Frontend (Vitest + Testing Library) :** composants clés (tableau de l'explorateur, formulaire d'ordre, carte de score).
- **Test de fumée** (Playwright) : l'application démarre, l'accueil, l'explorateur et une fiche s'affichent.

---

## 10. SEO et préparation à la mise en ligne (lot 5)
En local, aucune indexation n'est possible (les moteurs ont besoin d'une adresse publique). On prépare :
- **Structure sémantique :** balises `header`/`nav`/`main`/`footer`, un seul `h1` par page, hiérarchie `h2`/`h3` respectée, textes alternatifs.
- **Métadonnées par page :** `title`, `meta description`, `canonical`, Open Graph et Twitter Cards.
- **robots.txt** : mode configurable ; en local ou privé → tout interdire ; en ligne → autoriser uniquement les pages publiques. Pages privées (portefeuille, assistant, réglages) toujours en `noindex`.
- **sitemap.xml** généré par l'API à partir des pages publiques.
- **schema.org (JSON-LD) :** `WebApplication` pour l'accueil, `Corporation` (avec `tickerSymbol`) pour les fiches d'actions, `InvestmentFund` pour les ETF, `BreadcrumbList`.
- **llms.txt** : description du site destinée aux moteurs IA.
- **Performance :** objectif Lighthouse ≥ 90 (performance, accessibilité, bonnes pratiques, SEO).
- **À la mise en ligne :** pré-génération (prerendering) des pages publiques pour une indexation fiable ; vérification du cadre AMF si des recommandations sont publiées au grand public.

---

## 11. Découpage en lots
Chaque lot fait l'objet de son propre plan de développement et se termine par une application fonctionnelle.

| Lot | Contenu | Résultat |
|---|---|---|
| **1. Socle** | Docker Compose, PostgreSQL + migrations, utilisateur par défaut, univers et éligibilité, fournisseur Yahoo, worker de rafraîchissement, API de base, layout frontend | Les données se remplissent et s'affichent dans une liste simple |
| **2. Découverte** | Indicateurs et score, accueil (top 10, indices, carte du marché), explorateur, ETF, fiche action avec graphiques, favoris, réglages de base | Première version utilisable au quotidien |
| **3. Portefeuille** | Ordres, frais, positions, graphiques, compteur X/12 | Suivi complet du PEA |
| **4. Assistant IA** | Chat, panneau latéral, outils, streaming, coûts | IA intégrée |
| **5. SEO & mise en ligne** | Section 10 | Prêt à être publié |
| **6. Documentation** | `CLAUDE.md` à la racine (généré avec le skill `init` / `claude-md-improver`) : but du site, architecture, arborescence, commandes (lancer, tester, migrer), conventions, points d'attention (éligibilité, score, fournisseur Yahoo) | Les prochaines sessions avec Claude démarrent avec le contexte complet |

Évolutions ultérieures envisagées : import CSV des ordres, comptes utilisateurs, alertes, second fournisseur de données.
