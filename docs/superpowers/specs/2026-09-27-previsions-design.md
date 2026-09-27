# Prévisions court terme — conception

**Date :** 2026-09-27

**Demande de l'utilisateur :**
- un nouvel onglet, sans API externe, avec des **prédictions** (1 jour, 1 semaine, 1 mois) triables pour « parier à l'avance » ;
- les **statistiques historiques** qui les justifient, sous forme de tableau ;
- l'organisation et le visuel sont laissés au choix de Claude.

## 1. Principe

1. **Des signaux techniques** simples et connus sont calculés chaque jour pour chaque action, uniquement à partir des cours et des volumes jusqu'à ce jour-là, jamais après. Exemples : cassure du plus haut 20 jours avec volume, survente dans une tendance haussière, croisement des moyennes 50/200.
2. **Statistiques historiques** : pour chaque signal et chaque horizon (1, 5 et 21 séances), on mesure sur 5 ans ce qui a suivi ses apparitions :
   - nombre de cas ;
   - pourcentage de hausses ;
   - gain moyen et gain médian ;
   - gain après frais ;
   - pourcentage de cas au-dessus du CAC 40.

   La ligne de référence, « toutes les actions, n'importe quel jour », sert de point de comparaison.
3. **Prédiction** d'une action pour un horizon :
   - **gain attendu** : la moyenne des gains historiques de ses signaux actifs, pondérée par le nombre de cas et ramenée vers la moyenne générale quand un signal a peu de cas ;
   - **probabilité de hausse** : calculée de la même manière ;
   - **fiabilité** : celle de son signal le plus solide.

   Une action sans signal actif n'a pas de prédiction.
4. **Bulletin de notes :**
   - **Test sur l'année écoulée** :
     - les statistiques sont recalculées **sans** la dernière année ;
     - chaque jour de cette année, on simule le top 10 des prédictions de hausse et on mesure ce qui s'est réellement passé ;
     - le résultat est comparé à toutes les actions liquides sur les mêmes jours.
   - **Suivi réel** : chaque matin, les prédictions sont enregistrées. Elles sont vérifiées automatiquement quand l'horizon est atteint.

Partout, les résultats sont présentés comme des **statistiques et estimations, pas des certitudes ni des conseils**.

## 2. Signaux

Tous les signaux sont calculés sur les clôtures quotidiennes et les volumes (pandas, sans aucune donnée postérieure au jour t).

| Clé | Sens | Condition au jour t |
|---|---|---|
| `breakout_20` | hausse | clôture > plus haute clôture des 20 séances précédentes **et** volume > 1,5 × volume moyen sur 20 séances |
| `trend_strong` | hausse | clôture > MM50 > MM200 **et** performance sur 63 séances > +10 % |
| `oversold_uptrend` | hausse | RSI(14) < 30 **et** clôture > MM200 |
| `golden_cross` | hausse | MM50 est passée au-dessus de MM200 au cours des 5 dernières séances |
| `macd_cross_up` | hausse | MACD passe au-dessus de sa ligne de signal ce jour-là |
| `drop_week` | hausse (rebond) | performance sur 5 séances ≤ −10 % |
| `high_52w` | hausse | clôture ≥ plus haute clôture des 252 dernières séances |
| `volume_surge_up` | hausse | variation du jour ≥ +4 % **et** volume ≥ 2 × volume moyen sur 20 séances |
| `breakdown_20` | baisse | clôture < plus basse clôture des 20 séances précédentes **et** volume > 1,5 × volume moyen sur 20 séances |
| `trend_weak` | baisse | clôture < MM50 < MM200 **et** performance sur 63 séances < −10 % |
| `overbought` | baisse | RSI(14) > 75 |
| `death_cross` | baisse | MM50 est passée sous MM200 au cours des 5 dernières séances |
| `macd_cross_down` | baisse | MACD passe sous sa ligne de signal ce jour-là |
| `surge_week` | baisse (repli) | performance sur 5 séances ≥ +15 % |

Le « sens » est l'intuition courante. **Les statistiques disent ce qui s'est réellement passé**, même quand c'est l'inverse de l'intuition.

## 3. Calculs

- **Univers :**
  - actions (`kind = stock`) actives ;
  - un jour t ne compte que si le titre était liquide ce jour-là : montant moyen échangé sur 20 séances ≥ `min_turnover_eur` ;
  - ce filtre au jour t évite de ne garder que les titres encore liquides aujourd'hui.
- **Rendement futur :** `clôture(t+h) / clôture(t) − 1`, avec h ∈ {1, 5, 21} séances du titre.
  - Écart au CAC 40 : même calcul sur l'indice `^FCHI`, aux mêmes dates.
  - Les observations aberrantes (|rendement| > 100 %, souvent des erreurs de données ou des divisions d'actions mal corrigées) sont exclues.
- **Frais aller-retour :** 2 × le taux de la grille de l'utilisateur pour un ordre de référence de **500 €** (0,96 % avec la grille par défaut).
  - « Après frais » = rendement − frais.
  - « Gagnant après frais » = rendement > frais.
- **Fiabilité d'un couple (signal, horizon) :**
  - on calcule `t = moyenne_écart / (écart_type_écart / √n_eff)` ;
  - `n_eff = n / h` corrige le chevauchement des fenêtres ;
  - **élevée** si |t| ≥ 3 et n ≥ 200, **moyenne** si |t| ≥ 2 et n ≥ 100, **faible** sinon.
- **Prédiction :**
  - chaque signal actif s a un poids `w_s = n_eff_s / (n_eff_s + 50)` (moins de cas, moins de poids) ;
  - gain attendu = `base + Σ w_s·n_eff_s·(moy_s − base) / Σ n_eff_s` ;
  - la probabilité de hausse suit la même formule, avec les taux de hausse ;
  - la fiabilité est celle du signal actif au |t| le plus grand.
- **Rythme :**
  - les statistiques et le test de l'année écoulée sont recalculés si la dernière exécution a plus de 7 jours ;
  - les prédictions du jour et la vérification des anciennes sont faites chaque matin après l'historique quotidien (7 h 30), et au démarrage si c'est en retard.

## 4. Données

- **`forecast_runs`** : `id`, `computed_at`, `data_until`, `cutoff`, `round_trip_cost`, `stats` (JSON), `baseline` (JSON), `backtest` (JSON). Seule la dernière exécution est lue.
- **`forecasts`** : une ligne par (titre, jour, horizon), unique.
  - `security_id`, `as_of`, `horizon` ;
  - `expected_return`, `prob_up`, `reliability`, `signals` (JSON), `rank` ;
  - `base_close`, `actual_return` (vide tant que l'horizon n'est pas atteint), `resolved_on`.
- Ces données ne sont pas personnelles, donc pas de `user_id`. Le coût des frais vient de la grille de l'utilisateur par défaut au moment du calcul.

## 5. API

- `GET /api/forecasts` : prédictions du dernier jour calculé (titre, cours, signaux, et pour chaque horizon : gain attendu, probabilité, fiabilité, rang).
- `GET /api/forecasts/signals` : tableau des statistiques (signaux × horizons, plus la référence et les frais).
- `GET /api/forecasts/track-record` : test sur l'année écoulée et suivi réel, pour chaque horizon.
- `GET /api/securities/{id}/forecast` : signaux actifs et prédictions d'un titre, pour sa fiche.
- **Avant le premier calcul** : réponses vides avec `as_of: null`. Le frontend affiche alors « premier calcul en cours ».

## 6. Interface

- **Nouvel onglet « Prévisions »** dans la navigation, entre ETF et Portefeuille, à l'adresse `/previsions`.
- **En haut de page** : un bandeau d'avertissement (« estimations statistiques, pas des certitudes ni des conseils ») et la date des données.
- **Trois sous-onglets**, mémorisés dans l'adresse avec `?vue=` :
  1. **Prédictions** :
     - tableau virtualisé, triable par gain attendu à 1 jour, 1 semaine et 1 mois (1 semaine par défaut), par probabilité ou par fiabilité ;
     - chaque ligne montre le titre, le cours, les signaux actifs, puis pour chaque horizon le gain attendu et la probabilité de hausse, et enfin la fiabilité ;
     - filtres : recherche, éligibles PEA uniquement (coché par défaut), sens (hausse, baisse, tous), fiabilité minimale ;
     - un clic ouvre la fiche du titre.
  2. **Statistiques des signaux** :
     - choix de l'horizon (1 j, 1 sem, 1 mois) ;
     - tableau triable avec : signal et explication, sens, nombre de cas, % de hausses, gain moyen, gain médian, après frais, % au-dessus du CAC 40, fiabilité ;
     - la ligne « Toutes les actions (référence) » reste en tête.
  3. **Bulletin de notes** :
     - test sur l'année écoulée, par horizon (% de gagnants, gain moyen, après frais, écart avec toutes les actions), avec une phrase de verdict en français simple ;
     - suivi réel depuis la première prédiction, avec un état vide explicite.
- **Fiche d'un titre** : une carte « Prévisions court terme » montre les signaux actifs et les 3 horizons, avec un lien vers l'onglet.
- **SEO** : `/previsions` est toujours en `noindex` et absente du sitemap, par prudence réglementaire (AMF).

## 7. Correctif inclus

Dans le tri par nom de l'explorateur, les noms qui commencent par un chiffre (2CRSI, 74SOFTWARE…) passaient après Z. Le tri sera « naturel » et en français.

## 8. Hors périmètre

- Actualités et mots-clés sous les plus fortes variations.
- Outil « prévisions » pour l'assistant.
- Alertes.
- Prévisions sur les ETF.
