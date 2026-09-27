# Moteur de prévisions

Code : `backend/app/services/forecast/` (pandas/numpy, sans API externe), tâches dans `backend/app/jobs/forecasts.py`. Spécification complète : `docs/superpowers/specs/2026-09-27-previsions-design.md`.

## Signaux (`signals.py`)

14 signaux booléens, calculés pour chaque séance **uniquement avec les données disponibles ce jour-là**. Un test vérifie qu'aucune donnée future n'est utilisée. Un indicateur dont la fenêtre n'est pas complète donne toujours « faux ».

| Clé | Intuition | Condition au jour t |
|---|---|---|
| `breakout_20` | hausse | clôture > plus haute clôture des 20 séances précédentes **et** volume > 1,5 × moyenne 20 j |
| `trend_strong` | hausse | clôture > MM50 > MM200 **et** perf. 63 séances > +10 % |
| `oversold_uptrend` | hausse | RSI 14 &lt; 30 **et** clôture > MM200 |
| `golden_cross` | hausse | MM50 passée au-dessus de MM200 dans les 5 dernières séances |
| `macd_cross_up` | hausse | MACD passe au-dessus de son signal ce jour-là |
| `drop_week` | rebond | perf. 5 séances ≤ −10 % |
| `high_52w` | hausse | clôture ≥ plus haute clôture des 252 séances |
| `volume_surge_up` | hausse | variation du jour ≥ +4 % **et** volume ≥ 2 × moyenne 20 j |
| `breakdown_20` | baisse | clôture &lt; plus basse clôture des 20 séances précédentes **et** volume > 1,5 × moyenne |
| `trend_weak` | baisse | clôture &lt; MM50 &lt; MM200 **et** perf. 63 séances &lt; −10 % |
| `overbought` | baisse | RSI 14 > 75 |
| `death_cross` | baisse | MM50 passée sous MM200 dans les 5 dernières séances |
| `macd_cross_down` | baisse | MACD passe sous son signal ce jour-là |
| `surge_week` | repli | perf. 5 séances ≥ +15 % |

## Statistiques (`stats.py`, `engine.py`)

Pour chaque couple (signal, horizon), avec les horizons **1d = 1**, **1w = 5** et **1m = 21 séances** :

- **Univers :** actions actives ou radiées (pour éviter le biais du survivant). Un jour t ne compte que si le titre était **liquide ce jour-là** : montant moyen échangé sur 20 séances, **converti en euros** (les actions d'Oslo cotent en couronnes), ≥ `MIN_TURNOVER_EUR`.
- **Rendement futur** `r = clôture(t+h) / clôture(t) − 1`. Les observations avec |r| > 100 % sont exclues, car ce sont presque toujours des erreurs de données.
- **Écart au CAC 40** `x = r − r(^FCHI)` aux mêmes dates.
- **Mesures :** `n`, moyenne, médiane, % de hausses, écart moyen au CAC, % au-dessus du CAC, % gagnants après frais.
- **Frais aller-retour** = 2 × le taux de la grille de l'utilisateur pour un ordre de référence de **500 €** (0,96 % par défaut).
- **Référence `__all__`** : toutes les actions liquides, tous les jours.

### Fiabilité

```text
relatif = écart_moyen_du_signal − écart_moyen_de_la_référence
n_eff   = n / h                     # les fenêtres de cas voisins se chevauchent
t       = relatif / (écart_type / √n_eff)
```

| Fiabilité | Condition |
|---|---|
| `elevee` | \|t\| ≥ 3 et n ≥ 200 |
| `moyenne` | \|t\| ≥ 2 et n ≥ 100 |
| `faible` | sinon |

?> La fiabilité compare le signal à **l'action moyenne**, pas au CAC 40. Si toutes les actions ont battu l'indice sur la période, un signal qui fait pareil n'apporte aucune information.

## Prédiction (`predict.py`)

Pour une action et un horizon, avec ses signaux actifs `s` :

```text
w_s      = n_eff_s / (n_eff_s + 50)                        # peu de cas → peu de poids
attendu  = base.moyenne + Σ w_s · n_eff_s · (moy_s − base.moyenne) / Σ n_eff_s
proba    = base.%hausses + Σ w_s · n_eff_s · (%hausses_s − base.%hausses) / Σ n_eff_s   (bornée entre 0 et 1)
fiabilité = celle du signal actif au |t| le plus grand
```

Sans signal actif, pas de prédiction.

## Test sur l'année écoulée (walk-forward)

`run_analysis()` dans `engine.py` :

1. **Date de coupure** : 252 séances avant la dernière donnée.
2. **Statistiques d'entraînement** calculées uniquement sur les cas dont la fenêtre **se termine avant** la coupure.
3. Pour chaque jour après la coupure, on prédit avec ces seules statistiques, on retient les **10 meilleures prédictions de hausse** et on mesure le rendement réel.
4. Comparaison avec la moyenne de **toutes les actions liquides les mêmes jours** : `edge = gain moyen des choix − gain moyen de toutes les actions`.

## Exécution

| Tâche | Quand | Durée |
|---|---|---|
| `forecast_stats` : statistiques complètes et test | si la dernière exécution a plus de 7 jours, dans les tâches de 7 h 30 et 18 h 15 | ≈ 45 s |
| `forecasts` : prédictions du jour et vérification des anciennes | chaque soir à 18 h 15 après les clôtures, chaque matin à 7 h 30, et au démarrage si en retard | ≈ 10 s |

- Seules les **séances clôturées** sont utilisées (`last_session_close`) : une barre prise en pleine séance n'est pas un cours de clôture.
- Relancer le même jour **remplace** les prédictions du jour.
- La vérification relit départ et arrivée dans l'historique stocké. Après une division d'action, l'historique est rechargé à la nouvelle échelle et le calcul reste juste.

## Stockage et API

- `forecast_runs` : une ligne par calcul complet (statistiques et test en JSON, coupure, frais). Seule la dernière est lue.
- `forecasts` : une ligne par (titre, jour, horizon), avec rendement attendu, probabilité, fiabilité, signaux, rang, puis `actual_return` et `resolved_on` une fois l'horizon atteint.
- Routes : voir [API REST](api.md?id=prévisions). Avant le premier calcul, les réponses sont vides avec `as_of: null`.
- `/previsions` est toujours en `noindex` et absente du sitemap, par prudence réglementaire (AMF).
