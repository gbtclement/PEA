# Prévisions court terme — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Prévisions" tab with:
- short-term predictions (1 day, 1 week, 1 month) that can be sorted;
- the historical statistics of the technical signals behind them;
- a report card (backtest over the past year, then real tracking).

No external API is used.

**Architecture:**
- The calculation is pure pandas in `services/forecast/`: signals, then statistics, then prediction, then backtest.
- A worker job:
  - recomputes the statistics once a week;
  - each morning, records the day's predictions and checks the old ones.
- A FastAPI router `/api/forecasts` serves the data. The React page `/previsions` has three sub-tabs, and the stock page gets a card.

**Tech Stack:** pandas, numpy, SQLAlchemy, Alembic, FastAPI, React 19, TanStack Table/Virtual, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-27-previsions-design.md` (the formulas, signals and screens are the reference).

## Global Constraints

- **Horizons**: 1, 5 and 21 sessions, keyed `"1d"`, `"1w"`, `"1m"` in the API.
- **No look-ahead**:
  - a signal on day t only uses data up to t;
  - the backtest's training statistics only use observations whose window ends before `cutoff`.
- **Statistics universe**: active stocks that are liquid on day t (20-day average turnover ≥ `min_turnover_eur`). Outliers with |r| > 100 % are excluded.
- **Fees**: round trip = 2 × the fee-grid rate for a 500 € order.
- **UI**: French and light theme. No card is clipped from 1024 px up, and the column headers stay aligned (e2e tests `layout.spec.ts` and `table.spec.ts`). `/previsions` is `noindex` and absent from the sitemap.
- **Wording**: "estimation" and "statistiques", never "conseil". There is a warning banner on the page.

## Review Focus

1. Look-ahead bias:
   - appending future sessions must not change past signals;
   - the backtest must not use test-year statistics.
2. A stock with a short or gappy history (< 252 sessions, missing volumes) must not crash, and signals that need MM200 or 252 sessions must stay false.
3. The very first start (no run, no forecast): the API returns empty data with `as_of: null`, and the page says "premier calcul en cours".
4. The job runs twice on the same day: no duplicate forecasts (upsert); a forecast for a stock that is later delisted stays unresolved without crashing.
5. Huge tables: the predictions list (hundreds of rows) is virtualized and aligned; the statistics table (15 rows) is readable at 1100 px.

---

### Task 0: Natural name sort in the screener

**Files:** Modify `frontend/src/features/screener/columns.tsx`. Test: `frontend/src/features/screener/columns.test.ts` (new).

- [ ] Write a test: sorting the `name` column in ascending order puts `2CRSI` and `74SOFTWARE` before `A2A`, and orders `Air Liquide` < `airbus` < `Zucchi` regardless of case.
- [ ] Run it and see it fail.
- [ ] Add `sortingFn: (a, b) => a.original.name.localeCompare(b.original.name, "fr", { numeric: true, sensitivity: "base" })` to the name column.
- [ ] Run it and see it pass; commit `fix: natural French sort for security names`.

### Task 1: Signals (pure)

**Files:** Create `backend/app/services/forecast/__init__.py`, `backend/app/services/forecast/signals.py`. Test: `backend/tests/test_forecast_signals.py`.

**Interfaces:** Produces:
- `SIGNALS: dict[str, SignalInfo]`, where `SignalInfo(label: str, description: str, bullish: bool)`. The keys and conditions are those of spec §2.
- `compute_signals(close: pd.Series, volume: pd.Series) -> pd.DataFrame`:
  - index = dates, one boolean column per signal;
  - volume can be NaN, and volume-based signals are then False;
  - indicators with an incomplete window give False.

- [ ] Write the tests (synthetic series built with `pd.bdate_range`):
  - `breakout_20`: flat then a jump with volume ×3 on the last day gives True that day; the same jump with normal volume gives False.
  - `oversold_uptrend`: a long rise (close > MM200) then a sharp drop over 10 sessions gives RSI < 30 and True.
  - `golden_cross`: True for 5 sessions after the crossing, then False.
  - `high_52w` and `trend_strong` are False when there are fewer than 252 or 200 sessions.
  - `drop_week` and `surge_week` follow the 5-session thresholds.
  - **No look-ahead**: `compute_signals(close[:n])` equals `compute_signals(close)[:n]` for n = 300.
  - A 30-session series with NaN volume produces no error and only False values.
- [ ] Implement with pandas:
  - `rolling`;
  - RSI with Wilder's `ewm(alpha=1/14, adjust=False)`;
  - MACD with `ewm(span=12/26/9, adjust=False)`;
  - crossings: `(a > b) & (a.shift() <= b.shift())`;
  - "within the last 5 sessions": `cross.rolling(5).max().astype(bool)`.
- [ ] Tests pass; commit `feat: technical signals for short-term forecasts`.

### Task 2: Statistics, reliability and prediction (pure)

**Files:** Create `backend/app/services/forecast/stats.py`, `backend/app/services/forecast/predict.py`. Test: `backend/tests/test_forecast_stats.py`.

**Interfaces:** Produces:
- `HORIZONS = {"1d": 1, "1w": 5, "1m": 21}`
- `forward_returns(close: pd.Series, h: int) -> pd.Series`: close(t+h)/close(t) − 1, NaN at the end of the series.
- `@dataclass SignalStat(signal: str, horizon: str, n: int, mean: float, median: float, hit_rate: float, mean_excess: float, beat_index: float, hit_after_fees: float, std_excess: float, reliability: str)` with `to_dict()`.
- `class StatsAccumulator(cost: float)`:
  - `add(signal: str, horizon: str, returns: np.ndarray, excess: np.ndarray)`;
  - `result() -> list[SignalStat]`.

  The special signal key `"__all__"` is the baseline.
- `reliability(mean_excess, std_excess, n, h) -> "elevee" | "moyenne" | "faible"` (spec §3).
- `predict(active: list[str], horizon: str, stats: dict[tuple[str, str], SignalStat]) -> Prediction | None`, where `Prediction(expected_return, prob_up, reliability, signals)`. It returns None when no active signal has stats.

- [ ] Write the tests:
  - `forward_returns` on [100, 110, 121] with h=1 gives [0.1, 0.1, NaN].
  - The accumulator gives the right n, mean, median, hit_rate, hit_after_fees (cost 0.01) and beat_index.
  - `reliability`: large n with a strong signal gives `elevee`; n=50 gives `faible`; horizon 21 lowers n_eff.
  - `predict`:
    - with one signal, the result lies between the baseline and the signal's mean (shrinkage);
    - a signal with 10 cases barely moves the prediction;
    - two signals give a weighted average;
    - a bearish signal with a negative mean gives a negative expected return;
    - with no signal, the result is None.
- [ ] Implement. The accumulator concatenates numpy arrays per key and computes at `result()`.
- [ ] Tests pass; commit `feat: signal statistics, reliability and prediction`.

### Task 3: Full calculation and backtest (pure, over a set of series)

**Files:** Create `backend/app/services/forecast/engine.py`. Test: `backend/tests/test_forecast_engine.py`.

**Interfaces:** Produces:
- `@dataclass SeriesInput(security_id: int, close: pd.Series, volume: pd.Series)`
- `run_analysis(series: list[SeriesInput], index_close: pd.Series, min_turnover: float, cost: float, cutoff: date | None) -> Analysis`:
  - `Analysis.stats: list[SignalStat]`, computed over all the history;
  - `Analysis.baseline`, the `"__all__"` stats per horizon;
  - `Analysis.backtest: dict[horizon, BacktestResult]`. `BacktestResult` has: `days`, `picks`, `hit_rate`, `mean_return`, `mean_after_fees`, `mean_excess`, `baseline_mean`, `edge` = mean_return − baseline_mean.
  - `cutoff` defaults to the date 252 sessions before the end of the index.
- `latest_predictions(series, stats_by_key, as_of: date) -> list[tuple[int, str, Prediction]]`: predictions from the signals active on each series' last session, only when that session equals `as_of`.

- [ ] Write the tests with 3 or 4 synthetic series:
  - Liquidity filter: a series with a tiny volume counts nowhere.
  - Outliers: a ×3 jump is excluded from the stats.
  - **Backtest without look-ahead**:
    - build a series where `drop_week` is followed by a fall before the cutoff and by a rise after it;
    - the backtest must use the pre-cutoff stats, so it predicts a fall and does not pick the stock in the top 10;
    - `Analysis.stats`, computed over everything, shows the full mix.
  - `latest_predictions` ignores a series whose last session is older than `as_of`.
- [ ] Implement:
  - for each series: signals, forward returns per horizon, index excess aligned on dates (`reindex`), then the day-t liquidity mask;
  - accumulate twice: into `all` for everything, and into `train` only when `t + h` falls before the cutoff (use the series' own date at position t+h);
  - backtest: for each test date, predict each stock with the `train` stats, then take the 10 best `expected_return > 0` per horizon and read their real forward return;
  - baseline: the average of all liquid stocks on the same date.
- [ ] Tests pass; commit `feat: forecast engine with walk-forward backtest`.

### Task 4: Storage and worker jobs

**Files:**
- Create: `backend/app/models/forecast.py`, a migration `backend/alembic/versions/*_forecasts.py`, `backend/app/repositories/forecasts.py`, `backend/app/jobs/forecasts.py`.
- Modify: `backend/app/models/__init__.py`, `backend/app/jobs/scheduler.py`.
- Test: `backend/tests/test_forecast_jobs.py`.

**Interfaces:** Produces:
- the models `ForecastRun` and `Forecast` (spec §4), with a unique constraint `(security_id, as_of, horizon)`;
- `refresh_forecast_stats(ctx) -> int` (number of stats) and `refresh_forecasts(ctx) -> int` (predictions written plus predictions resolved);
- the repository `latest_run(session)`, `latest_as_of(session)`, `forecasts_for(session, as_of)`.

- [ ] Write the tests (factories plus `make_ctx`, and daily prices inserted over about 300 sessions):
  - `refresh_forecast_stats` creates a run with its stats, baseline and backtest, and the cost comes from the default grid (0.0096).
  - `refresh_forecasts`:
    - writes one row per (stock with a signal, horizon), with a `rank` per horizon (1 = best expected return);
    - run again the same day: no duplicates;
    - resolution: after adding 5 sessions, the `1w` forecasts get `actual_return` and `resolved_on`, while the `1m` ones stay unresolved;
    - with no run, `refresh_forecasts` first calls `refresh_forecast_stats`.
- [ ] Implement and wire the scheduler:
  - `daily_job`: after `_refresh_scores`, `run_job(ctx, "forecast_stats", ...)` when the last run is older than 7 days, then `run_job(ctx, "forecasts", refresh_forecasts)`;
  - `bootstrap_job`: the same after the history, when `forecasts` is older than the last session close.
- [ ] Run `alembic upgrade head` and the full backend suite; commit `feat: forecasts stored daily and checked when due`.

### Task 5: API

**Files:** Create `backend/app/schemas/forecasts.py`, `backend/app/api/routes/forecasts.py`. Modify `main.py`. Test: `backend/tests/test_api_forecasts.py`.

**Interfaces:** the 4 routes of spec §5.
- `/api/forecasts` returns `{as_of, round_trip_cost, rows: [{security: {id, name, symbol, market, eligibility, price, change_pct}, signals: [{key, label, bullish}], horizons: {"1d": {expected_return, prob_up, reliability, rank} | null, ...}}]}`.
- `/signals` returns `{as_of, round_trip_cost, signals: [{key, label, description, bullish, horizons: {"1d": SignalStatOut, ...}}], baseline: {"1d": SignalStatOut, ...}}`.
- `/track-record` returns `{simulated: {"1d": BacktestOut, ...}, real: {"1d": {picks, hit_rate, mean_return, mean_after_fees, baseline_mean, first_day} | null, ...}}`. Real metrics are computed on forecasts with `rank <= 10` that are resolved and have `expected_return > 0`; `baseline_mean` is the average of all resolved forecasts on the same days.
- `/securities/{id}/forecast` returns `{as_of, signals, horizons}`, or 404 when the security is unknown.

- [ ] Write the tests: empty state (`as_of: None`, empty lists), a populated state with a seeded run and forecasts, rows ordered by `1w` rank, track record, and the security endpoint including an unknown security.
- [ ] Implement, then regenerate the frontend types (`npm run gen:api` with the dev API running).
- [ ] Commit `feat: forecasts API`.

### Task 6: "Prévisions" page

**Files:**
- Modify: `ScreenerTable.tsx` and `columns.tsx` (make the table generic, `ColumnSpec<T>`), `app/router.tsx`, `app/Sidebar.tsx`.
- Create: `features/forecasts/api.ts`, `ForecastsPage.tsx`, `PredictionsView.tsx`, `SignalStatsView.tsx`, `TrackRecordView.tsx`, `ForecastsPage.test.tsx`.
- Rename `features/screener/ScreenerTable.tsx` to `components/DataTable.tsx`, generic.

**Interfaces:**
- `DataTable<T>({ rows, columns: ColumnSpec<T>[], sorting, onSortingChange, onRowClick, getRowId? })`.
- The page uses `usePageMeta({ title: "Prévisions court terme", description, noindex: true })`.

- [ ] Write the tests:
  - the Prévisions nav link, and the `h1` "Prévisions court terme" plus the warning banner;
  - "premier calcul en cours" when `as_of` is null;
  - the predictions view is sorted by 1 week by default; clicking "1 mois" re-sorts; the "Éligibles PEA" filter hides a non-eligible stock;
  - the statistics view has the reference row first; switching to "1 jour" changes the numbers;
  - the report card shows the verdict and the real-tracking empty state;
  - `noindex` is set.
- [ ] Implement:
  - sub-tabs with `?vue=predictions|statistiques|bulletin`;
  - horizon cells: signed % coloured up/down, with `58 % de hausse` in small text below;
  - the reliability badge: élevée in green, moyenne in amber, faible in grey;
  - signal chips: up in green, down in red, at most 3 shown plus "+n".
- [ ] Add `/previsions` to the lists in `e2e/layout.spec.ts`, `e2e/seo.spec.ts` (NOINDEX) and `e2e/table.spec.ts`.
- [ ] Vitest, tsc, rebuild, e2e; commit `feat: Prévisions page with predictions, signal statistics and report card`.

### Task 7: Stock page card and documentation

**Files:** Create `features/security/ForecastCard.tsx`. Modify `SecurityPage.tsx`, `SecurityPage.test.tsx`, `README.md`, `CLAUDE.md`.

- [ ] Write the tests: the card shows the active signals and the 3 horizons; with no signal it says "Aucun signal actif aujourd'hui"; the link points to `/previsions`.
- [ ] Implement. The card goes in the grid after the simulator.
- [ ] Update the README (Prévisions feature) and `CLAUDE.md` (`services/forecast`, no look-ahead, weekly and daily rhythm).
- [ ] Full suites; commit `feat: short-term forecast card on stock pages`.
