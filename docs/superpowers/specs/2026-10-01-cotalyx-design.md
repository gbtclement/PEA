# Cotalyx : application grand public, enveloppes, historique complet, univers étendu

Date : 2026-10-01. Remplace la notion « PEA Radar » partout ; complète le spec d'origine (`2026-09-26-pea-radar-design.md`), qui reste la référence pour tout ce qui n'est pas modifié ici.

## Objectif

L'application va sortir au grand public. Elle ne doit plus être centrée sur une seule enveloppe (le PEA) :

- nouveau nom **Cotalyx** (cotalyx.com et cotalyx.fr libres au 2026-10-01, vérification INPI à faire par l'utilisateur) ;
- le PEA devient **une enveloppe parmi d'autres**, choisie dans les réglages ;
- le graphique et le simulateur d'une fiche acceptent des durées libres et l'historique complet ;
- l'univers de titres s'élargit (ETF européens, autres places européennes, États-Unis) ;
- tout élément cliquable affiche le curseur « main ».

Avertissement « outil d'aide à la décision, pas un conseil en investissement » : inchangé, toujours présent.

## Découpage

Une branche par bloc, PR à la fin de chaque bloc, arrêt après chaque bloc (l'utilisateur fait `/compact`).

| Bloc | Branche | Contenu |
|---|---|---|
| A | `cotalyx` | curseur, renommage Cotalyx, textes neutres |
| B | `enveloppes` | modèle des enveloppes, PEA-PME, réglages, top 10, Explorer, admin |
| C | `historique-complet` | historique max, graphique 10A / Max / personnalisé, simulateur à durée libre |
| D | `univers-etendu` | ETF Euronext, autres places européennes, États-Unis, devises, horaires de séance |

L'ordre compte : C avant D pour que les nouveaux titres de D récupèrent directement tout leur historique.

---

## Bloc A — Curseur et renommage

### A1. Curseur

Règle CSS globale (feuille de base Tailwind, `@layer base`) :

- `cursor: pointer` sur `button`, `a[href]`, `select`, `summary`, `label[for]`, `input[type=checkbox|radio|range|file|submit|button]`, `[role=button|tab|link|menuitem|option|switch|checkbox|radio]` ;
- `cursor: not-allowed` sur ces mêmes éléments quand ils sont `:disabled` ou `[aria-disabled=true]`.

Vérifié dans le navigateur sur : réglages du profil, réglages admin, select de l'Explorer, onglets, menus.

### A2. Renommage

- **Nom affiché** : « Cotalyx » partout (titre, layout, `usePageMeta`, mails, pages légales, guide, documentation admin, `llms.txt`, manifest, README, CLAUDE.md). Les CGU/CGV changent : bump de `TERMS_VERSION` et `LEGAL_UPDATED`.
- **Textes neutres** : plus de « PEA » dans les accroches, le SEO, l'écran d'inscription (« suivre votre PEA » → « suivre vos investissements »), « Mon PEA » → « Mon portefeuille ». Le PEA ne reste cité que là où il s'agit vraiment de l'enveloppe (badge, filtre, guide `bourse/pea.md`).
- **Portefeuille** : la règle « X ordres par an » est présentée comme une règle de frais du courtier, sans mention du PEA. La grille Crédit Agricole reste la valeur par défaut, décrite comme un exemple modifiable.
- **Assistant IA** : le prompt système ne suppose plus un PEA ; il reçoit les enveloppes choisies par l'utilisateur (bloc B ; d'ici là, contexte neutre). Descriptions des outils mises à jour.
- **Identifiants techniques** : cookies `pea_session`, `pea_csrf`, `pea_device`, `pea_oauth`, `pea_google_pending` → préfixe `cotalyx_`. Conséquence assumée : tout le monde est déconnecté une fois et les appareils connus redeviennent « nouveaux » (une alerte « nouvel appareil » possible par compte). Paquet Python `pea-radar` → `cotalyx`.
- **Non modifiés** (signalés à l'utilisateur, à lui de décider) : nom du dépôt GitHub, nom de la base et de l'utilisateur PostgreSQL (`pea_radar`, `pea`), nom du dossier local. Les renommer casserait le volume existant sans rien apporter au public.

Tests : les tests qui cherchent « PEA » dans les métadonnées ou les cookies sont adaptés ; un test vérifie qu'aucun texte de page publique (titre, description) ne contient « PEA Radar ».

---

## Bloc B — Enveloppes

### B1. Liste des enveloppes

| Code | Libellé | Pays | Règle (automatique, une correction manuelle prime toujours) |
|---|---|---|---|
| `pea` | PEA | France | action : siège UE/EEE et soumise à l'IS (règle actuelle de `services/eligibility/rules.py`) ; ETF : liste confirmée de `seeds/` + correction admin |
| `pea_pme` | PEA-PME | France | éligible PEA **et** moins de 5 000 salariés **et** CA ≤ 1,5 Md€ **et** capitalisation < 1 Md€. Estimation, présentée comme telle. Donnée manquante → « à vérifier » |
| `cto` | Compte-titres | — | tous les titres |

Écartées volontairement : assurance-vie et PER (dépendent du contrat de l'assureur), ISA, PIR et autres enveloppes étrangères (public visé : France). Le registre est un dictionnaire de règles en code (`ENVELOPES`) : ajouter une enveloppe = une règle + une entrée.

### B2. Données

- Nouvelle table `security_envelopes(security_id, envelope, status, source, override)` avec `status ∈ {eligible, a_verifier, non_eligible}`, `source ∈ {auto, seed, manual}`, clé `(security_id, envelope)`. Seules les enveloppes à règle (`pea`, `pea_pme`) y ont des lignes ; `cto` n'est pas stocké.
- Migration : les colonnes `securities.eligibility`, `eligibility_source`, `eligibility_override` sont recopiées dans des lignes `pea`, puis supprimées.
- Fondamentaux : ajout de `employees` (`fullTimeEmployees`) et `revenue` (`totalRevenue`, converti en euros) depuis Yahoo, pour la règle PEA-PME. Recalcul des enveloppes après chaque mise à jour des fondamentaux.
- Le worker suit désormais les cours de **tous** les titres actifs (le filtre « non éligible au PEA » de `repositories/market_data.py` disparaît).
- Réglages utilisateur : colonne `envelopes` (liste de codes) sur les réglages de l'utilisateur, vide par défaut.

### B3. Comportement

- **Réglages** : carte « Mes enveloppes » (cases à cocher PEA, PEA-PME, Compte-titres) avec une phrase d'explication. Rien de coché, ou Compte-titres coché = tous les titres.
- **Top 10 du moment** : `eligible_for_top` ne dépend plus de l'éligibilité PEA (seulement liquidité et historique ≥ 200 jours). Le filtre par enveloppe s'applique à la lecture, selon les réglages de l'utilisateur connecté ; visiteur = tous les titres. Même règle pour les classements (`rankings.py`) et le contexte de l'assistant.
- **Explorer / ETF** : le filtre « Éligibilité » devient « Enveloppe : Toutes / PEA / PEA-PME ». Les options « À vérifier » et « Non éligibles » disparaissent. Un titre « à vérifier » n'apparaît pas dans le filtre PEA.
- **Badges** : « Éligible PEA » → « PEA », plus « PEA-PME ». Pas de badge pour « à vérifier » ni « non éligible ». Sur la fiche, une ligne discrète rappelle que l'éligibilité est déduite et à confirmer auprès de sa banque.
- **Admin** : la carte devient « Enveloppes — corrections manuelles » : choix de l'enveloppe puis du statut (éligible / à vérifier / non éligible / automatique). Route `PATCH /api/securities/{id}/envelopes/{code}`.
- **Prévisions** : la case « Éligibles PEA uniquement » devient « Mes enveloppes uniquement », cochée par défaut si l'utilisateur en a choisi.
- **SEO** (`seo.py`, sitemap) : plus de filtre sur l'éligibilité PEA, tous les titres actifs.

Tests : règle PEA-PME (fonction pure, cas limites et données manquantes), migration des données existantes, filtre du top 10 selon les réglages, visiteur, filtre Explorer, route admin.

---

## Bloc C — Historique complet, graphique, simulateur

### C1. Historique

- `history_years` est remplacé par un historique **complet** : premier chargement d'un titre en `period="max"` côté Yahoo.
- Rattrapage des titres existants : tâche ponctuelle (puis idempotente) qui charge, pour chaque titre, les cours antérieurs à sa première date stockée. Elle tourne sous `HEAVY_JOBS_LOCK`, par paquets, avec les pauses Yahoo, et peut reprendre là où elle s'est arrêtée (un titre déjà rattrapé est marqué `history_complete`).
- Volume : la table `daily_prices` fait 196 Mo pour 5 ans et 1 900 titres ; à compter environ ×3 à ×5 pour l'historique complet sur cet univers (à multiplier par la taille de l'univers du bloc D, voir D5).
- Les prévisions gardent leur fenêtre actuelle (5 ans + 30 jours) : elles ne lisent pas tout l'historique.

### C2. Graphique de la fiche

- Périodes : 1J · 1S · 1M · 6M · 1A · 5A · **10A** · **Max** · **Personnalisé**.
- Personnalisé : deux champs date (début, fin, bornés à l'historique disponible), appliqués par un bouton. L'API accepte `period=custom&start=…&end=…` (fin ≥ début, sinon 422).
- Les indicateurs (SMA50, SMA200, RSI, MACD) restent calculés sur tout l'historique puis coupés à la fenêtre, comme aujourd'hui.
- Au-delà de ~2 500 points, les barres sont regroupées par semaine (10A) ou par mois (Max, personnalisé > 10 ans) côté API, pour garder un graphique fluide.

### C3. Simulateur « Et si j'avais investi »

- Boutons rapides inchangés (1 semaine, 1 mois, 6 mois, 1 an), plus « Autre durée » : un nombre + une unité (jours, semaines, mois, ans). Exemples : 2 semaines, 5 ans, 10 ans.
- API : `GET /simulate?amount=…&duration=10&unit=years` (les anciennes valeurs `period` restent acceptées). Durée plafonnée à l'historique disponible ; au-delà, le simulateur part de la première cotation et le dit (« historique disponible depuis le … »).

Tests : découpage des périodes (10A, Max, personnalisé, erreurs), regroupement des points, durées du simulateur et plafond, rattrapage idempotent (faux fournisseur).

---

## Bloc D — Univers étendu

Constat (2026-10-01) : Yahoo ne fournit pas de liste de titres, la limite vient de nos sources. L'univers actuel = liste officielle des actions Euronext (~1 800) + CSV saisis à la main (quelques actions Xetra/Madrid, 18 ETF, 3 indices).

### D1. Sources

| Source | État | Usage |
|---|---|---|
| Actions Euronext | en place | inchangé |
| ETF Euronext | page officielle protégée par un anti-robot | même formulaire que les actions si un point d'accès CSV fonctionne ; sinon instantané versionné dans `seeds/` (comme `euronext_snapshot.csv`), rafraîchi à la main avec un script documenté |
| États-Unis (NYSE, Nasdaq, NYSE Arca) | `nasdaqtraded.txt` de Nasdaq Trader, public, ~13 300 lignes dont ~5 800 ETF | tâche univers ; exclusion des titres de test, warrants, droits, unités, préférentielles |
| Autres places européennes (Xetra, Madrid, SIX, Londres, Nasdaq Nordic, Vienne, Varsovie) | sources à identifier en début de bloc | une source par place avec repli sur instantané ; une place sans source fiable est reportée et signalée |

Chaque source est un fournisseur derrière une interface commune (`ListingProvider`) ; une source en panne ne vide jamais l'univers (règle actuelle conservée, par source).

### D2. Éligibilité des nouveaux titres

- Actions : règle par ISIN inchangée (une action américaine sort « non éligible PEA » automatiquement).
- ETF : un ETF n'est éligible au PEA que s'il est confirmé (`seeds/`, correction admin) ou si son nom contient « PEA » ; sinon « à vérifier ». Jamais d'éligibilité déduite du pays de l'émetteur (les ETF UCITS irlandais ou luxembourgeois ne sont pas éligibles par défaut).

### D3. Devises

`services/fx.py` (table fixe, EUR et NOK) devient une table de cours de change mise à jour chaque jour depuis Yahoo (`EURUSD=X`, `EURGBP=X`, `EURCHF=X`, `EURSEK=X`, `EURDKK=X`, `EURPLN=X`, `EURNOK=X`…), stockée en base, avec repli sur la dernière valeur connue. La devise d'un titre vient de sa place de cotation (ou de la source quand elle la donne). Pence britanniques (GBp) gérés.

### D4. Séances

`market_calendar.py` ne connaît que Paris. Il gère désormais un calendrier par place (Europe : horaires actuels ; États-Unis : 15 h 30 – 22 h heure de Paris, jours fériés américains). Les paliers de cours T1/T2/T3 ne rafraîchissent que les titres dont la place est ouverte ; le passage du soir des titres américains a lieu après leur clôture (vers 22 h 30).

### D5. Volume et débit

- Univers visé : de l'ordre de 20 000 à 25 000 titres (×10 à ×13).
- Historique complet : de l'ordre de 5 à 10 Go pour `daily_prices`. **À valider par l'utilisateur avant le rattrapage** au regard de l'hébergement prévu ; option de repli : historique complet pour les actions, 10 ans pour les ETF.
- Débit Yahoo : les paliers de cours restent dans leurs intervalles grâce au découpage par séance ; les fondamentaux (lents) sont étalés sur la semaine au lieu d'un passage quotidien complet. Mesure du temps de chaque tâche avant/après, consignée dans la PR.
- Le premier chargement du nouvel univers tourne en arrière-plan ; l'application reste utilisable pendant ce temps (les titres sans cours n'apparaissent pas dans les listes).

Tests : analyse de chaque source (fichiers d'exemple), exclusions US, règle ETF, conversion de devises, calendrier par place, paliers qui ignorent les places fermées.

---

## Hors périmètre

- Renommage du dépôt GitHub, de la base et du dossier local.
- Assurance-vie, PER, enveloppes étrangères.
- Cotations en temps réel (les cours restent différés).
- Dépôt de marque et achat des noms de domaine (à faire par l'utilisateur).
