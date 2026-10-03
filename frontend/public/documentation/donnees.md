# Données et worker

## L'univers des titres

Il n'existe **aucune liste officielle complète** des titres éligibles au PEA ni au PEA-PME, et les données du Crédit Agricole sont hors de portée : connexion bancaire et conditions d'utilisation. L'univers est donc **reconstruit** (`jobs/universe.py`) à partir de plusieurs listes publiques, une par place. Il compte environ **20 000 titres**.

| Source (`securities.source`) | Places | Fichier téléchargé | Secours |
|---|---|---|---|
| `euronext` | Actions Euronext : Paris, Amsterdam, Bruxelles, Milan, Lisbonne, Dublin, Oslo | formulaire CSV d'Euronext | `seeds/euronext_snapshot.csv` |
| `euronext_etf` | ETF Euronext (dont « ETF Plus », le segment ETF de Milan) | même formulaire, page des ETF | `seeds/listings/euronext_etf.csv` |
| `us` | États-Unis : NYSE, NYSE American, NYSE Arca, Nasdaq | `nasdaqtraded.txt` de Nasdaq Trader (sans warrants, droits, unités, préférentielles ni titres de test) | `seeds/listings/us.csv` |
| `xetra` | Francfort (Xetra) : actions et ETF | « All tradable instruments » de Deutsche Börse | `seeds/listings/xetra.csv` |
| `six` | Bourse suisse : actions et ETF | listes CSV publiques de SIX | `seeds/listings/six.csv` |
| `nordic` | Stockholm, Helsinki, Copenhague, Islande | écran des actions de l'API publique de nasdaq.com | `seeds/listings/nordic.csv` |
| `seed` | Actions saisies à la main (Madrid…), ETF confirmés PEA, indices | `seeds/extra_stocks.csv`, `seeds/etfs.csv`, `seeds/indices.csv` | — |

Règles :

- **Une source en panne ne vide jamais l'univers** : si le téléchargement échoue (ou renvoie trop peu de lignes), l'instantané local prend le relais. Si même l'instantané manque, les titres de cette source restent actifs et la tâche `universe` signale l'échec ; les autres sources se mettent à jour quand même.
- **Un titre par ISIN** : un même titre coté sur plusieurs places n'apparaît qu'une fois, sur sa place d'origine (SAP à Francfort, ABB à Zurich), puis dans cet ordre : Euronext, ETF Euronext, Nordic, SIX, Xetra, États-Unis. Une action cotée hors de chez elle (Apple à Francfort) est écartée quand sa place d'origine est suivie ; sinon elle est gardée (les actions autrichiennes, via Xetra). Une société non européenne cotée à Francfort ou Zurich (Shopify, Toyota) n'est gardée que si la liste américaine manque : sa cotation américaine suffit. Quand une source tombe en panne, ses ISIN restent à elle : une autre place ne reprend pas ses titres (favoris et ordres compris).
- **Devise** : celle que donne la source (`securities.currency`, par exemple `USD` pour un ETF de Francfort coté en dollars), sinon celle de la place.
- Un ticker inconnu de Yahoo n'a jamais de cours : il reste **caché** des listes et de la recherche.

Rafraîchir les instantanés (dans le conteneur `api`, puis commiter les fichiers) :

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api python -m app.seeds.snapshots
```

!> **Places reportées** : Londres (le fichier change d'adresse chaque mois), Madrid et Vienne (pages HTML seulement), Varsovie (site injoignable). Elles seront ajoutées quand une source stable existera. Les 34 actions de Madrid de `seeds/extra_stocks.csv` restent suivies.

Le ticker Yahoo est construit avec le suffixe de la place : `.PA`, `.AS`, `.BR`, `.MI`, `.LS`, `.IR`, `.OL`, `.DE`, `.SW`, `.ST`, `.HE`, `.CO`, `.IC`, `.MC` ; sans suffixe aux États-Unis (`BRK.B` devient `BRK-B`).

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

`services/market_calendar.py` : un calendrier (`Calendar`) par place, `calendar_for_market()` choisit le bon.

- **Europe** (toutes les places européennes, et les indices) : séance de **9 h 00 à 17 h 35**, heure de Paris, jours ouvrés ; jours fériés Euronext calculés (dont Pâques), clôture anticipée à **14 h 05** les 24 et 31 décembre.
- **New York** : séance de **9 h 30 à 16 h 00 heure de New York**, soit 15 h 30 – 22 h 00 à Paris la plupart de l'année (14 h 30 – 21 h 00 pendant les deux ou trois semaines où les changements d'heure ne coïncident pas). Jours fériés américains (Martin Luther King, Presidents' Day, Vendredi saint, Memorial Day, Juneteenth, 4 juillet, Labor Day, Thanksgiving, Noël, avec report au vendredi ou au lundi) ; clôture à 13 h le lendemain de Thanksgiving, le 3 juillet et le 24 décembre.
- `last_session_close()` donne la dernière clôture européenne passée. Elle sert à savoir si une donnée est à jour et à n'utiliser que des séances **terminées** pour les prévisions.

## Les cours de change

`services/fx.py` convertit en euros (liquidité, capitalisation, PEA-PME, simulateur, portefeuille). La tâche `fx` lit chaque jour les cours Yahoo `EURUSD=X`, `EURGBP=X`, `EURCHF=X`, `EURSEK=X`, `EURDKK=X`, `EURNOK=X`, `EURPLN=X`, `EURISK=X`, `EURJPY=X`, `EURAUD=X`, `EURCAD=X`, `EURSGD=X` et les range dans la table `fx_rates`. Si Yahoo ne répond pas, la dernière valeur stockée reste en place ; sans aucune valeur, une table fixe sert de repli. Les cotations en pence (`GBp`, `GBX`) valent un centième de livre.

## Les tâches du worker

Planifiées dans `jobs/scheduler.py` (APScheduler, fuseau Paris) :

| Tâche | Quand | Ce qu'elle fait |
|---|---|---|
| `bootstrap` | Au démarrage du worker | Rattrape ce qui manque ou a vieilli, puis charge tous les cours et calcule les scores |
| `universe` | 7 h 00, lundi à vendredi | Met à jour la liste des titres et leurs enveloppes, puis lance `history_backfill` pour charger les nouveaux titres |
| `daily` | 7 h 30, lundi à vendredi | Cours de change (`fx`) → historique journalier → scores → prévisions → fondamentaux (un cinquième des actions chaque jour : chacune est relue une fois par semaine, les jamais chargées d'abord) |
| `evening` | 18 h 15, lundi à vendredi | Cours de change → clôtures officielles des titres européens → scores → prévisions. Le soir et le week-end, l'app affiche ainsi les chiffres exacts de la dernière séance, fixing de clôture compris |
| `us_evening` | 22 h 30, lundi à vendredi | Après la clôture de New York : cours de change → clôtures officielles des titres américains (`daily_history_us`) → scores → prévisions |
| `history_backfill` | 20 h 00 tous les jours, après `universe` et à la fin de `bootstrap` | Historique complet des titres pas encore marqués `history_complete` : un nouveau titre est chargé en entier, un ancien titre reçoit ses cours antérieurs à sa première date stockée. Par paquets de 50 titres, en reprenant le verrou des tâches lourdes **à chaque paquet** ; un seul rattrapage à la fois. Un titre que Yahoo ne renvoie pas est abandonné après 30 jours. Ne fait plus rien une fois tout rattrapé |
| `quotes_t1` | Toutes les minutes, **pendant la séance de sa place** | Cours des indices, favoris, titres détenus et top 10 (tous titres, PEA, PEA-PME) |
| `quotes_t2` | Toutes les 5 min, en séance | Cours des 150 titres les plus échangés, **puis recalcul des scores** des titres dont la place est ouverte |
| `quotes_t3` | Toutes les 5 min, en séance | Cours de tous les autres titres dont la place est ouverte |

Détails :

- Les tâches **lourdes** (univers, historique, fondamentaux, et chaque paquet du rattrapage) passent l'une après l'autre grâce au verrou `HEAVY_JOBS_LOCK`. Elles ne se marchent pas dessus et ne saturent pas Yahoo. Le **premier chargement** du nouvel univers (environ 18 000 historiques complets) dure plusieurs heures : il rend le verrou entre deux paquets, si bien que les autres tâches passent pendant ce temps et que l'application reste utilisable (un titre sans cours n'apparaît pas dans les listes).
- Les paliers de cours ne demandent que les titres **dont la place est ouverte** : le matin l'Europe, de 15 h 30 à 17 h 35 l'Europe et New York, le soir New York seul. Les notifications de forte variation (N1) suivent la même règle.
- Une tâche quotidienne manquée (PC en veille) est rattrapée si le PC se réveille dans les **3 heures**. Au-delà, c'est `bootstrap` qui rattrape au prochain démarrage, y compris les clôtures américaines de 22 h 30 (`daily_history_us`).
- Le worker suit les cours de **tous** les titres actifs, quelle que soit leur enveloppe.
- Chaque exécution passe par `jobs/runner.py`, qui enregistre dans `data_status` la dernière réussite, la dernière erreur et le nombre d'éléments traités. C'est ce que lit `GET /api/status`.
- L'historique est **complet** : `history_backfill` charge un nouveau titre depuis sa première cotation, puis le passage quotidien ajoute les nouvelles séances. Après une division d'action détectée (ou des cours réajustés par Yahoo), toute la série du titre est rechargée à la nouvelle échelle. Les statistiques des prévisions ne lisent que les 5 dernières années.

## Les paliers de rafraîchissement

Calculés dans `jobs/tiers.py`, parmi les titres dont la place est ouverte :

- **T1** : indices, favoris, titres détenus dans le portefeuille, top 10 ;
- **T2** : les `TIER2_SIZE` (150) titres suivants, classés par montant moyen échangé sur 20 séances ;
- **T3** : tout le reste.

## Les caches de l'API

L'intraday (graphique 1J) et les actualités sont demandés à Yahoo **à la demande**, puis mis en cache mémoire (`services/cache.py`, `TTLCache`) pour ne pas refaire la requête à chaque affichage.
