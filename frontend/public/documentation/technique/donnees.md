# Données et worker

## L'univers des titres

Il n'existe **aucune liste officielle complète** des titres éligibles au PEA, et les données du Crédit Agricole sont hors de portée : connexion bancaire et conditions d'utilisation. L'univers est donc **reconstruit** (`jobs/universe.py`, `seeds/loader.py`) :

1. **Actions Euronext** (Paris, Amsterdam, Bruxelles, Milan, Lisbonne, Dublin, Oslo), téléchargées depuis Euronext. Si le téléchargement échoue, l'instantané `seeds/euronext_snapshot.csv` sert de secours.
2. **Actions hors Euronext** des grands indices, par exemple du DAX (`.DE`) ou de l'IBEX (`.MC`) : `seeds/extra_stocks.csv`.
3. **ETF éligibles PEA** : `seeds/etfs.csv`.
4. **Indices** (CAC 40, SBF 120, Euro Stoxx 50) : `seeds/indices.csv`.

Le ticker Yahoo est construit avec le suffixe de la place : `.PA`, `.AS`, `.BR`, `.MI`, `.LS`, `.IR`, `.OL`, `.DE`, `.MC`.

!> Ne **jamais** scraper le site du Crédit Agricole.

## Le fournisseur Yahoo

`providers/yahoo.py` utilise la bibliothèque `yfinance`, derrière l'interface `MarketDataProvider` de `providers/base.py`. Un autre fournisseur pourrait être branché sans toucher aux services.

- Source gratuite et non officielle, **limitée en débit** :
  - requêtes par paquets de `YAHOO_CHUNK_SIZE` titres ;
  - pause de `YAHOO_PAUSE_SECONDS` entre deux paquets ;
  - pause de `FUNDAMENTALS_PAUSE_SECONDS` entre deux titres pour les fondamentaux.
- **3 tentatives** avec attente doublée à chaque échec (`providers/retry.py`).
- Cours **différés**, pas du temps réel.
- Une panne est détectée et enregistrée dans `data_status`. L'interface continue d'afficher les dernières données avec leur date.

## Le calendrier de bourse

`services/market_calendar.py`, fuseau `Europe/Paris` :

- séance de **9 h 00 à 17 h 35**, jours ouvrés ;
- jours fériés Euronext calculés (dont Pâques), avec clôture anticipée à **14 h 05** certains jours ;
- `last_session_close()` donne la dernière clôture passée. Elle sert à savoir si une donnée est à jour et à n'utiliser que des séances **terminées** pour les prévisions.

## Les tâches du worker

Planifiées dans `jobs/scheduler.py` (APScheduler, fuseau Paris) :

| Tâche | Quand | Ce qu'elle fait |
|---|---|---|
| `bootstrap` | Au démarrage du worker | Rattrape ce qui manque ou a vieilli, puis charge tous les cours et calcule les scores |
| `universe` | 7 h 00, lundi à vendredi | Met à jour la liste des titres et leur éligibilité |
| `daily` | 7 h 30, lundi à vendredi | Historique journalier → scores → prévisions → fondamentaux |
| `quotes_t1` | Toutes les 2 min, **en séance** | Cours des indices, favoris, titres détenus et top 10 |
| `quotes_t2` | Toutes les 5 min, en séance | Cours des 150 titres les plus échangés, **puis recalcul des scores** |
| `quotes_t3` | Toutes les 30 min, en séance | Cours de tous les autres titres |

Détails :

- Les tâches **lourdes** (univers, historique, fondamentaux) passent l'une après l'autre grâce au verrou `HEAVY_JOBS_LOCK`. Elles ne se marchent pas dessus et ne saturent pas Yahoo.
- Une tâche quotidienne manquée (PC en veille) est rattrapée si le PC se réveille dans les **3 heures**. Au-delà, c'est `bootstrap` qui rattrape au prochain démarrage.
- Chaque exécution passe par `jobs/runner.py`, qui enregistre dans `data_status` la dernière réussite, la dernière erreur et le nombre d'éléments traités. C'est ce que lit `GET /api/status`.
- L'historique est conservé sur **5 ans**. Après une division d'action détectée, l'historique du titre est rechargé à la nouvelle échelle.

## Les paliers de rafraîchissement

Calculés dans `jobs/tiers.py` :

- **T1** : indices, favoris, titres détenus dans le portefeuille, top 10 ;
- **T2** : les `TIER2_SIZE` (150) titres suivants, classés par montant moyen échangé sur 20 séances ;
- **T3** : tout le reste.

## Les caches de l'API

L'intraday (graphique 1J) et les actualités sont demandés à Yahoo **à la demande**, puis mis en cache mémoire (`services/cache.py`, `TTLCache`) pour ne pas refaire la requête à chaque affichage.
