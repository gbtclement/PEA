# Cotalyx bloc C — Historique complet, graphique, simulateur — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store each security's full price history, let the chart show 10 years / Max / a custom range, and let the simulator take any duration.

**Architecture:** The Yahoo provider accepts `start=None` (period `max`). New securities load their whole history at once. Existing ones are caught up by an idempotent `history_backfill` job that marks each finished security `history_complete`. The history route picks a window (fixed period or custom dates) and groups bars by week or month when there are more than 2,500 of them. The simulate route accepts `duration` + `unit` next to the old `period`, and says so when the history starts later than asked.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, APScheduler, yfinance; React 19, TanStack Query, Vitest, Playwright; Docsify.

**Spec:** `docs/superpowers/specs/2026-10-01-cotalyx-design.md` (section « Bloc C »).

## Global Constraints

- Branch `historique-complet`, created from `master`; PR against `master` at the end. Stop after the block.
- Interface text, comments and docs in French; commits in English (conventional commits), ending with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Never open or print `.env`. Never modify an existing Alembic migration.
- Do not modify files under `.superpowers/` or `docs/superpowers/` except this plan and its ledger.
- Chart periods: 1J · 1S · 1M · 6M · 1A · 5A · **10A** · **Max** · **Personnalisé**. API: `period=custom&start=…&end=…`, end ≥ start, otherwise 422.
- Indicators (SMA50, SMA200, RSI, MACD) stay computed on the whole history, then cut to the window.
- Above ~2,500 points: weekly bars (10A), monthly bars (Max, custom > 10 years), grouped by the API.
- Simulator: quick buttons unchanged (1 semaine, 1 mois, 6 mois, 1 an) plus « Autre durée » (number + jours/semaines/mois/ans). API `GET /simulate?amount=…&duration=10&unit=years`; old `period` values still accepted. Beyond the history: start at the first close and say « historique disponible depuis le … ».
- Forecast statistics keep their window (5 years + 30 days); they do not read the whole history.
- Backfill runs under `HEAVY_JOBS_LOCK`, in batches, with the Yahoo pauses, and resumes where it stopped (`history_complete`).
- Test commands:
  - backend: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q` (one file: append the path);
  - frontend (in `frontend/`): `npx tsc -b`, `npx vitest run`, `npx oxlint`;
  - API types: `npm run gen:api` (dev API on :8000 must run the new code: `docker compose up -d --build api` first);
  - e2e: `docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --build api worker web` then `npm run e2e` in `frontend/`; afterwards restore with `docker compose up -d --build api worker web`.

## Review Focus

1. A custom range entirely outside the stored history (e.g. 1990 for a stock listed in 2005) must return 200 with no bars, and the chart shows its « Pas de données » message, not an error. Test: `test_history_custom_range_outside_history` (Task 3).
2. Grouped bars must keep indicator lines aligned: each line point's time is a bar time, ascending, without duplicates (lightweight-charts throws otherwise). Test: `test_history_10y_groups_by_week` (Task 3).
3. A backfill where Yahoo's prices were readjusted since the 5-year load (dividend, split) must not leave a jump at the junction: the whole series is replaced. Test: `test_backfill_replaces_a_readjusted_series` (Task 2).
4. Month arithmetic in the simulator: 31 March minus 1 month is 28 or 29 February, and a huge duration must not crash. Test: `test_months_before_clamps_day_and_floor` (Task 4).
5. A stock with less history than asked, in both the simulator (note) and the 5A window (5A now really means 5 years, not "everything"). Tests: `test_simulate_beyond_history_starts_at_first_close`, `test_history_5y_keeps_five_years` (Tasks 4 and 3).

---

### Task 1: Full history on first load, `history_complete` flag

**Files:**
- Modify: `backend/app/providers/base.py:79`, `backend/app/providers/yahoo.py:191-193`, `backend/tests/fakes.py:33,41`
- Modify: `backend/app/models/security.py`, `backend/app/repositories/market_data.py`, `backend/app/jobs/market.py:65-100`
- Modify: `backend/app/core/config.py:17` (remove `history_years`), `backend/app/jobs/forecasts.py:38`
- Create: `backend/alembic/versions/d7f9b1c3e5a7_history_complete.py`
- Test: `backend/tests/test_yahoo.py`, `backend/tests/test_market_jobs.py`, `backend/tests/test_migration_history_complete.py`

**Interfaces:**
- Produces: `MarketDataProvider.get_daily_history(tickers: list[str], start: date | None) -> dict[str, list[DailyBar]]` (None = whole history); `Security.history_complete: bool`; `mark_history_complete(session, security_ids: list[int]) -> None`; `first_price_dates(session, security_ids: list[int]) -> dict[int, date]`; `incomplete_history_securities(session) -> list[Security]`; `price_date_range(session, security_id: int) -> tuple[date | None, date | None]`; `_is_readjusted` unchanged.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_yahoo.py`, after `test_get_daily_history_passes_start`:

```python
def test_get_daily_history_without_start_loads_everything():
    seen = {}

    def fake_download(tickers, **kwargs):
        seen.update(kwargs)
        return multi({t: frame(ROWS) for t in tickers})

    provider = YahooProvider(download=fake_download, sleep=lambda s: None)
    provider.get_daily_history(["A.PA"], None)
    assert seen["period"] == "max" and "start" not in seen
```

In `backend/tests/test_market_jobs.py`, replace `test_history_reloads_after_split` and `test_history_backfill_then_incremental` with the versions below, and add `test_incremental_refresh_keeps_history_incomplete`:

```python
def test_history_reloads_after_split(db, make_ctx):
    security = make_security(db, "C.PA")
    db.add(DailyPrice(security_id=security.id, date=date(2026, 9, 24), open=90, high=90, low=90, close=90.0, volume=1))
    db.add(DailyPrice(security_id=security.id, date=date(2026, 9, 25), open=100, high=100, low=100, close=100.0, volume=1))
    db.flush()
    market = SplitMarket()
    refresh_daily_history(make_ctx(market=market, now=NOW))
    assert market.history_calls[-1] == (["C.PA"], None)  # rechargé en entier
    closes = db.scalars(select(DailyPrice.close).where(DailyPrice.security_id == security.id).order_by(DailyPrice.date)).all()
    assert closes == [9.0, 10.0]
    db.expire_all()
    assert db.get(Security, security.id).history_complete is True


def test_history_backfill_then_incremental(db, make_ctx):
    security = make_security(db, "C.PA")
    bars = [DailyBar(date(2026, 9, 24), 1, 1, 1, 1.0, 10), DailyBar(date(2026, 9, 25), 1, 1, 1, 2.0, 10)]
    market = FakeMarket(history={"C.PA": bars})
    ctx = make_ctx(market=market, now=NOW)
    refresh_daily_history(ctx)
    assert market.history_calls[0] == (["C.PA"], None)  # premier chargement : tout l'historique
    db.expire_all()
    assert db.get(Security, security.id).history_complete is True
    refresh_daily_history(ctx)
    assert market.history_calls[1] == (["C.PA"], date(2026, 9, 25))
    count = db.scalar(select(func.count()).select_from(DailyPrice).where(DailyPrice.security_id == security.id))
    assert count == 2


def test_incremental_refresh_keeps_history_incomplete(db, make_ctx):
    security = make_security(db, "C.PA")
    add_prices(db, security, 10.0, 10, days=2)
    market = FakeMarket(history={"C.PA": [DailyBar(date(2026, 9, 25), 10, 10, 10, 10.0, 10)]})
    refresh_daily_history(make_ctx(market=market, now=NOW))
    db.expire_all()
    assert db.get(Security, security.id).history_complete is False  # le rattrapage s'en charge
```

`SplitMarket.get_daily_history` (just above `test_history_reloads_after_split`) currently branches on `start`; keep it, its reload branch is the one taken when `start` is not the last stored day, which includes `None`. Read it before running and adjust only if it compares `start` to a date in a way that fails on `None`.

Create `backend/tests/test_migration_history_complete.py`:

```python
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings

PREVIOUS = "c5e7a9b1d3f5"
NAME = "pea_radar_migration_history_test"


@pytest.fixture
def migration_url():
    base = make_url(get_settings().test_database_url)
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {NAME} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {NAME}"))
    yield base.set(database=NAME).render_as_string(hide_password=False)
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {NAME} WITH (FORCE)"))
    admin.dispose()


def _config(url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = url
    return cfg


def test_existing_securities_start_with_incomplete_history(migration_url):
    cfg = _config(migration_url)
    command.upgrade(cfg, PREVIOUS)
    engine = create_engine(migration_url)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO securities (id, yahoo_ticker, symbol, name, kind, market, active, created_at, updated_at) "
                          "VALUES (1, 'MC.PA', 'MC', 'LVMH', 'stock', 'Euronext Paris', true, now(), now())"))
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT history_complete FROM securities WHERE id = 1")).scalar() is False
    command.downgrade(cfg, PREVIOUS)
    engine.dispose()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_yahoo.py tests/test_market_jobs.py tests/test_migration_history_complete.py`
Expected: FAIL — `seen["period"]` KeyError, history calls still use `date(2021, 9, 29)`, `history_complete` attribute/column missing.

- [ ] **Step 3: Implement**

`backend/app/providers/base.py`, the protocol line:

```python
    def get_daily_history(self, tickers: list[str], start: date | None) -> dict[str, list[DailyBar]]: ...  # None : tout l'historique
```

`backend/app/providers/yahoo.py`:

```python
    def get_daily_history(self, tickers: list[str], start: date | None) -> dict[str, list[DailyBar]]:
        window = {"period": "max"} if start is None else {"start": start.isoformat()}  # None : tout l'historique Yahoo
        frames = self._download_frames(tickers, interval="1d", **window)
```

(keep the existing `return` line after it). `backend/tests/fakes.py`: `self.history_calls: list[tuple[list[str], date | None]] = []` and `def get_daily_history(self, tickers: list[str], start: date | None)`.

`backend/app/models/security.py`, after `active`:

```python
    history_complete: Mapped[bool] = mapped_column(default=False)  # cours chargés depuis la première cotation
```

`backend/alembic/versions/d7f9b1c3e5a7_history_complete.py`:

```python
"""history: securities.history_complete for the full-history backfill

Revision ID: d7f9b1c3e5a7
Revises: c5e7a9b1d3f5
Create Date: 2026-10-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d7f9b1c3e5a7"
down_revision: Union[str, Sequence[str], None] = "c5e7a9b1d3f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Faux pour les titres existants : le rattrapage charge leurs cours antérieurs aux 5 ans déjà stockés.
    op.add_column("securities", sa.Column("history_complete", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("securities", "history_complete")
```

`backend/app/repositories/market_data.py` (add `update` to the sqlalchemy import if missing):

```python
def incomplete_history_securities(session: Session) -> list[Security]:
    return list(session.scalars(
        select(Security).where(Security.active.is_(True), Security.history_complete.is_(False)).order_by(Security.id)
    ))


def mark_history_complete(session: Session, security_ids: list[int]) -> None:
    if security_ids:
        session.execute(update(Security).where(Security.id.in_(security_ids)).values(history_complete=True))


def first_price_dates(session: Session, security_ids: list[int]) -> dict[int, date]:
    rows = session.execute(
        select(DailyPrice.security_id, func.min(DailyPrice.date))
        .where(DailyPrice.security_id.in_(security_ids)).group_by(DailyPrice.security_id)
    )
    return {security_id: first for security_id, first in rows}


def price_date_range(session: Session, security_id: int) -> tuple[date | None, date | None]:
    first, last = session.execute(
        select(func.min(DailyPrice.date), func.max(DailyPrice.date)).where(DailyPrice.security_id == security_id)
    ).one()
    return first, last
```

`backend/app/jobs/market.py`, `refresh_daily_history` becomes (import `mark_history_complete`; `timedelta` stays imported only if still used elsewhere in the file):

```python
def refresh_daily_history(ctx: JobContext) -> int:
    ids: dict[str, int] = {}
    # Clé None : titre sans aucun cours, chargé en entier (period="max").
    by_start: dict[date | None, list[str]] = defaultdict(list)
    with ctx.session_factory() as session:
        last_dates = latest_price_dates(session)
        for security in refreshable_securities(session):
            ids[security.yahoo_ticker] = security.id
            # On repart du dernier jour connu (inclus) pour corriger une séance incomplète.
            by_start[last_dates.get(security.id)].append(security.yahoo_ticker)
    total = 0
    received: set[str] = set()
    readjusted: list[str] = []
    for start, tickers in sorted(by_start.items(), key=lambda item: (item[0] is not None, item[0] or date.min)):
        history = ctx.market.get_daily_history(sorted(tickers), start)
        received.update(history)
        with ctx.session_factory() as session:
            complete: list[int] = []
            for ticker, bars in history.items():
                if start is not None and _is_readjusted(bars, start, stored_close(session, ids[ticker], start)):
                    readjusted.append(ticker)
                    continue
                total += upsert_daily_bars(session, ids[ticker], bars)
                if start is None:
                    complete.append(ids[ticker])
            mark_history_complete(session, complete)
            session.commit()
    if readjusted:
        history = ctx.market.get_daily_history(sorted(readjusted), None)
        with ctx.session_factory() as session:
            for ticker, bars in history.items():
                delete_daily_prices(session, ids[ticker])
                total += upsert_daily_bars(session, ids[ticker], bars)
            mark_history_complete(session, [ids[t] for t in history])
            session.commit()
    _write_closing_quotes(ctx, [ids[t] for t in received])
    _ensure_response(len(ids), len(received), "historiques")
    return total
```

`backend/app/core/config.py`: delete the `history_years: int = 5` line (`extra="ignore"` keeps an old `HISTORY_YEARS` in `.env` harmless).

`backend/app/jobs/forecasts.py`: add near the top-level constants

```python
# Les statistiques des signaux gardent 5 ans (+ marge) : elles ne lisent pas tout l'historique.
STATS_WINDOW = timedelta(days=365 * 5 + 30)
```

and replace line 38 with `since = today - STATS_WINDOW`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_yahoo.py tests/test_market_jobs.py tests/test_migration_history_complete.py tests/test_forecast_jobs.py`
Expected: PASS.

- [ ] **Step 5: Full backend suite, then commit**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
Expected: all pass (grep the tests for `history_years` first; none use it today).

```bash
git add backend
git commit -m "feat: load full price history for new securities and track history_complete"
```

---

### Task 2: Idempotent full-history backfill job

**Files:**
- Modify: `backend/app/jobs/market.py`, `backend/app/jobs/scheduler.py`
- Test: `backend/tests/test_history_backfill.py` (create), `backend/tests/test_scheduler.py`

**Interfaces:**
- Consumes: Task 1's `incomplete_history_securities`, `first_price_dates`, `mark_history_complete`, `get_daily_history(..., None)`, `_is_readjusted`, `stored_close`, `delete_daily_prices`, `upsert_daily_bars`, `_ensure_response`.
- Produces: `BACKFILL_BATCH: int = 100`; `backfill_history(ctx: JobContext) -> int` (rows written); `history_backfill_job(ctx)`; scheduler job id `history_backfill`; `data_status` job name `history_backfill`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_history_backfill.py`:

```python
from datetime import date

import pytest
from sqlalchemy import select

import app.jobs.market as market_module
from app.jobs.market import backfill_history
from app.models import DailyPrice, Security
from app.providers.base import DailyBar
from tests.factories import make_security
from tests.fakes import FakeMarket


def bar(day: date, close: float) -> DailyBar:
    return DailyBar(day, close, close, close, close, 10)


def store(db, security, day: date, close: float) -> None:
    db.add(DailyPrice(security_id=security.id, date=day, open=close, high=close, low=close, close=close, volume=1))
    db.flush()


def closes(db, security) -> list[tuple[date, float]]:
    return [tuple(row) for row in db.execute(
        select(DailyPrice.date, DailyPrice.close).where(DailyPrice.security_id == security.id).order_by(DailyPrice.date))]


def complete(db, security) -> bool:
    db.expire_all()
    return db.get(Security, security.id).history_complete


def test_backfill_adds_older_bars_and_marks_complete(db, make_ctx):
    security = make_security(db, "C.PA")
    make_security(db, "OLD.PA", active=False)
    store(db, security, date(2021, 1, 4), 50.0)
    market = FakeMarket(history={"C.PA": [bar(date(2000, 1, 3), 10.0), bar(date(2021, 1, 4), 50.0), bar(date(2021, 1, 5), 99.0)]})
    assert backfill_history(make_ctx(market=market)) == 1
    assert market.history_calls == [(["C.PA"], None)]
    # Seuls les cours antérieurs sont ajoutés ; les plus récents restent l'affaire du passage quotidien.
    assert closes(db, security) == [(date(2000, 1, 3), 10.0), (date(2021, 1, 4), 50.0)]
    assert complete(db, security) is True


def test_backfill_is_idempotent(db, make_ctx):
    security = make_security(db, "C.PA")
    store(db, security, date(2021, 1, 4), 50.0)
    market = FakeMarket(history={"C.PA": [bar(date(2000, 1, 3), 10.0), bar(date(2021, 1, 4), 50.0)]})
    ctx = make_ctx(market=market)
    backfill_history(ctx)
    assert backfill_history(ctx) == 0
    assert len(market.history_calls) == 1


def test_backfill_replaces_a_readjusted_series(db, make_ctx):
    security = make_security(db, "C.PA")
    store(db, security, date(2021, 1, 4), 50.0)
    store(db, security, date(2021, 1, 5), 52.0)
    # Yahoo a divisé l'action par deux depuis le premier chargement : la jonction ne colle plus.
    market = FakeMarket(history={"C.PA": [bar(date(2000, 1, 3), 5.0), bar(date(2021, 1, 4), 25.0), bar(date(2021, 1, 5), 26.0)]})
    backfill_history(make_ctx(market=market))
    assert closes(db, security) == [(date(2000, 1, 3), 5.0), (date(2021, 1, 4), 25.0), (date(2021, 1, 5), 26.0)]


def test_backfill_leaves_missing_tickers_for_next_run(db, make_ctx):
    found = make_security(db, "C.PA")
    missing = make_security(db, "X.PA")
    backfill_history(make_ctx(market=FakeMarket(history={"C.PA": [bar(date(2000, 1, 3), 10.0)]})))
    assert complete(db, found) is True
    assert complete(db, missing) is False


class FailsOnSecondCall(FakeMarket):
    def get_daily_history(self, tickers, start):
        if self.history_calls:
            raise ConnectionError("Yahoo KO")
        return super().get_daily_history(tickers, start)


def test_backfill_resumes_after_a_failure(db, make_ctx, monkeypatch):
    monkeypatch.setattr(market_module, "BACKFILL_BATCH", 1)
    first = make_security(db, "A.PA")
    second = make_security(db, "B.PA")
    history = {"A.PA": [bar(date(2000, 1, 3), 1.0)], "B.PA": [bar(date(2000, 1, 3), 2.0)]}
    with pytest.raises(ConnectionError):
        backfill_history(make_ctx(market=FailsOnSecondCall(history=history)))
    assert complete(db, first) is True and complete(db, second) is False
    market = FakeMarket(history=history)
    backfill_history(make_ctx(market=market))
    assert market.history_calls == [(["B.PA"], None)]
```

In `backend/tests/test_scheduler.py`, add `"history_backfill"` to the set in `test_build_scheduler_registers_jobs`, and add:

```python
def test_bootstrap_runs_history_backfill(db, make_ctx):
    fresh = {job: OPEN_MONDAY for job in ("universe", "daily_history", "fundamentals", "forecasts")}
    ctx, market, _ = seeded_ctx(db, make_ctx, OPEN_MONDAY, fresh)
    bootstrap_job(ctx)
    assert (["MC.PA"], None) in market.history_calls
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_history_backfill.py tests/test_scheduler.py`
Expected: FAIL — `ImportError: cannot import name 'backfill_history'`; scheduler set lacks `history_backfill`.

- [ ] **Step 3: Implement**

`backend/app/jobs/market.py` (import `first_price_dates`, `incomplete_history_securities`):

```python
# Titres par appel au fournisseur pendant le rattrapage ; chaque paquet est validé à part (reprise après une panne).
BACKFILL_BATCH = 100


def backfill_history(ctx: JobContext) -> int:
    """Rattrapage de l'historique complet : ajoute les cours antérieurs à la première date stockée."""
    with ctx.session_factory() as session:
        targets = [(s.yahoo_ticker, s.id) for s in incomplete_history_securities(session)]
    total = 0
    received = 0
    for offset in range(0, len(targets), BACKFILL_BATCH):
        batch = dict(targets[offset:offset + BACKFILL_BATCH])
        history = ctx.market.get_daily_history(sorted(batch), None)
        received += len(history)
        with ctx.session_factory() as session:
            firsts = first_price_dates(session, list(batch.values()))
            for ticker, bars in history.items():
                security_id = batch[ticker]
                first = firsts.get(security_id)
                if first is not None and _is_readjusted(bars, first, stored_close(session, security_id, first)):
                    # Yahoo a réajusté les cours depuis (dividende, division) : on remplace toute la série.
                    delete_daily_prices(session, security_id)
                    total += upsert_daily_bars(session, security_id, bars)
                else:
                    total += upsert_daily_bars(session, security_id, [b for b in bars if first is None or b.date < first])
            mark_history_complete(session, [batch[t] for t in history])
            session.commit()
    _ensure_response(len(targets), received, "historiques complets")
    return total
```

The Yahoo provider already pauses between its own chunks of 50 tickers, so a batch of 100 makes two downloads with a pause between them.

`backend/app/jobs/scheduler.py` (import `backfill_history`):

```python
def history_backfill_job(ctx: JobContext) -> None:
    """Historique complet des titres existants : ne fait plus rien une fois tous les titres rattrapés."""
    with HEAVY_JOBS_LOCK:
        run_job(ctx, "history_backfill", backfill_history)
```

At the end of `bootstrap_job`, after the last `with HEAVY_JOBS_LOCK:` block — **outside** it, at function level: `HEAVY_JOBS_LOCK` is a plain `threading.Lock`, not reentrant, so calling `history_backfill_job` inside that block deadlocks the worker:

```python
    history_backfill_job(ctx)  # rattrapage après tout le reste : les cours du jour passent d'abord
```

In `build_scheduler`, after the `evening` job:

```python
    scheduler.add_job(history_backfill_job, CronTrigger(hour=20, minute=0, timezone=tz),
                      args=[ctx], id="history_backfill", **daily)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_history_backfill.py tests/test_scheduler.py`
Expected: PASS. If `test_bootstrap_fills_empty_database_once` now records an error for `history_backfill` (FakeMarket has no history for the seeded indices), that is expected: `run_job` records the failure and the bootstrap goes on; the test must still pass unchanged.

- [ ] **Step 5: Full backend suite, then commit**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
Expected: all pass.

```bash
git add backend
git commit -m "feat: resumable full-history backfill job for existing securities"
```

---

### Task 3: History API — 10A, Max, custom range, grouped bars

**Files:**
- Create: `backend/app/services/price_window.py`
- Modify: `backend/app/api/routes/security_detail.py` (`Period`, `DAILY_WINDOW`, `get_history`), `backend/app/schemas/security_detail.py` (`HistoryOut`), `backend/app/services/assistant/tools.py` (`HISTORY_DAYS`, `_history`)
- Test: `backend/tests/test_price_window.py` (create), `backend/tests/test_api_security_detail.py`, `backend/tests/test_assistant_tools.py`

**Interfaces:**
- Consumes: Task 1's `price_date_range(session, security_id)`.
- Produces: `HistoryOut` gains `interval: Literal["5m", "30m", "day", "week", "month"]`, `first_date: date | None`, `last_date: date | None` (whole stored series, also on intraday responses). `GET /securities/{id}/history?period=1D|1W|1M|6M|1Y|5Y|10Y|MAX|custom&start=YYYY-MM-DD&end=YYYY-MM-DD`. Assistant `get_price_history` accepts `10Y` and `MAX`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_price_window.py`:

```python
from datetime import date, timedelta

from app.services.price_window import choose_interval, groups

MONDAY = date(2026, 9, 21)


def test_choose_interval():
    assert choose_interval(date(2016, 9, 25), date(2026, 9, 25), 2500) == "day"
    assert choose_interval(date(2016, 9, 25), date(2026, 9, 25), 2501) == "week"   # 10 ans
    assert choose_interval(date(2010, 1, 4), date(2026, 9, 25), 4200) == "month"   # au-delà de 10 ans


def test_groups_by_week_and_month():
    days = [MONDAY + timedelta(days=i) for i in range(10)]  # lundi 21/09 → mercredi 30/09
    assert groups(days, "day") == [[i] for i in range(10)]
    assert groups(days, "week") == [list(range(7)), [7, 8, 9]]
    assert groups(days, "month") == [list(range(10))]
    assert groups([date(2026, 9, 30), date(2026, 10, 1)], "month") == [[0], [1]]
```

In `backend/tests/test_api_security_detail.py`, replace `test_history_5y_returns_everything` and add the tests below; in `test_history_daily_with_indicators` add `assert body["interval"] == "day" and body["first_date"] == "2025-11-30" and body["last_date"] == "2026-09-25"` (300 days ending 2026-09-25 start on 2025-11-30).

```python
def get_history(client, security, **params):
    return client.get(f"/api/securities/{security.id}/history", params=params)


def test_history_5y_keeps_five_years(client, db):
    security = with_history(db, days=2000)
    body = get_history(client, security, period="5Y").json()
    assert len(body["bars"]) == 365 * 5 + 2  # 5 ans + 1 jour en arrière, jour de départ inclus
    max_body = get_history(client, security, period="MAX").json()
    assert len(max_body["bars"]) == 2000 and max_body["interval"] == "day"


def test_history_10y_groups_by_week(client, db):
    security = with_history(db, days=3700)
    body = get_history(client, security, period="10Y").json()
    assert body["interval"] == "week"
    times = [b["time"] for b in body["bars"]]
    assert 520 <= len(times) <= 524 and times == sorted(set(times))
    assert body["bars"][-1]["close"] == 100.0 + 3699  # dernière clôture de la dernière semaine
    for line in ("sma50", "sma200", "rsi"):
        assert {p["time"] for p in body[line]} <= set(times)
    assert {p["time"] for p in body["macd"]} <= set(times)


def test_history_max_groups_by_month_beyond_ten_years(client, db):
    security = with_history(db, days=4000)
    body = get_history(client, security, period="MAX").json()
    assert body["interval"] == "month"
    last = body["bars"][-1]
    assert last["time"] == "2026-09-01"
    assert last["volume"] == 10 * 25 and last["high"] == 100.0 + 3999 and last["open"] == 100.0 + 3999 - 24
    assert body["first_date"] == (LAST - timedelta(days=3999)).isoformat()


def test_history_custom_range(client, db):
    security = with_history(db)
    body = get_history(client, security, period="custom", start="2026-09-01", end="2026-09-10").json()
    assert [b["time"] for b in body["bars"]][0] == "2026-09-01" and body["bars"][-1]["time"] == "2026-09-10"
    assert len(body["bars"]) == 10 and body["interval"] == "day"
    assert len(body["sma200"]) == 10  # indicateurs calculés sur tout l'historique, puis coupés


def test_history_custom_range_requires_ordered_dates(client, db):
    security = with_history(db)
    assert get_history(client, security, period="custom", start="2026-09-01").status_code == 422
    assert get_history(client, security, period="custom", start="2026-09-10", end="2026-09-01").status_code == 422


def test_history_custom_range_outside_history(client, db):
    security = with_history(db)
    response = get_history(client, security, period="custom", start="1990-01-01", end="1990-12-31")
    assert response.status_code == 200 and response.json()["bars"] == []
```

In `backend/tests/test_assistant_tools.py`, in `test_price_history_sampled_with_indicators`, change the invalid period from `"10Y"` to `"2Y"` and append:

```python
    full = run_tool(db, user, "get_price_history", {"ticker": "MC.PA", "period": "MAX"})
    month = run_tool(db, user, "get_price_history", {"ticker": "MC.PA", "period": "1M"})
    assert full["first_date"] < month["first_date"] and full["closes"][-1]["close"] == 359.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_price_window.py tests/test_api_security_detail.py tests/test_assistant_tools.py`
Expected: FAIL — module `app.services.price_window` missing, 422 on `10Y`/`MAX`/`custom`, no `interval` key.

- [ ] **Step 3: Implement**

Create `backend/app/services/price_window.py`:

```python
"""Regroupement des barres journalières du graphique d'une fiche (semaine ou mois au-delà de ~2 500 points)."""
from datetime import date, timedelta
from typing import Literal

Interval = Literal["day", "week", "month"]

MAX_DAILY_POINTS = 2500  # au-delà, le graphique devient lent
WEEKLY_MAX_SPAN = timedelta(days=3660)  # jusqu'à 10 ans (et quelques jours) : une barre par semaine, sinon par mois


def choose_interval(first: date, last: date, count: int) -> Interval:
    if count <= MAX_DAILY_POINTS:
        return "day"
    return "week" if last - first <= WEEKLY_MAX_SPAN else "month"


def _key(day: date, interval: Interval) -> date:
    if interval == "week":
        return day - timedelta(days=day.weekday())
    if interval == "month":
        return day.replace(day=1)
    return day


def groups(days: list[date], interval: Interval) -> list[list[int]]:
    """Positions des jours (triés) regroupées par semaine ou par mois ; une position par groupe en journalier."""
    result: list[list[int]] = []
    previous: date | None = None
    for position, day in enumerate(days):
        key = _key(day, interval)
        if key != previous:
            result.append([])
            previous = key
        result[-1].append(position)
    return result
```

`backend/app/schemas/security_detail.py` (`Literal` and `date` imports as needed):

```python
class HistoryOut(BaseModel):
    period: str
    intraday: bool
    interval: Literal["5m", "30m", "day", "week", "month"]  # durée d'une barre
    first_date: date | None  # bornes de tout l'historique stocké (champs de la période personnalisée)
    last_date: date | None
    bars: list[Bar]
    sma50: list[LinePoint]
    sma200: list[LinePoint]
    rsi: list[LinePoint]
    macd: list[MacdPoint]
```

`backend/app/api/routes/security_detail.py` — replace `Period`, `DAILY_WINDOW` and `get_history` (import `DailyPrice` from `app.models`, `price_date_range` from `app.repositories.market_data`, `choose_interval, groups` from `app.services.price_window`):

```python
Period = Literal["1D", "1W", "1M", "6M", "1Y", "5Y", "10Y", "MAX", "custom"]
INTRADAY = {"1D": ("1d", "5m"), "1W": ("5d", "30m")}
DAILY_WINDOW = {"1M": 31, "6M": 183, "1Y": 365, "5Y": 365 * 5 + 1, "10Y": 365 * 10 + 2, "MAX": None}


def _merge(rows: list[DailyPrice], time: str) -> Bar:
    """Une barre pour plusieurs séances : ouverture de la première, clôture de la dernière, extrêmes et volume cumulés."""
    highs = [r.high for r in rows if r.high is not None]
    lows = [r.low for r in rows if r.low is not None]
    volumes = [r.volume for r in rows if r.volume is not None]
    return Bar(time=time, open=rows[0].open, high=max(highs) if highs else None, low=min(lows) if lows else None,
               close=rows[-1].close, volume=sum(volumes) if volumes else None)


@router.get("/securities/{security_id}/history", response_model=HistoryOut)
def get_history(
    security_id: int,
    period: Period = "6M",
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    provider: MarketDataProvider = Depends(get_market_provider),
) -> HistoryOut:
    security = _row_or_404(db, user.id if user else None, security_id)[0]
    if period == "custom":
        if start is None or end is None:
            raise HTTPException(status_code=422, detail="Indiquez une date de début et une date de fin.")
        if end < start:
            raise HTTPException(status_code=422, detail="La date de fin doit suivre la date de début.")
    first_date, last_date = price_date_range(db, security_id)
    if period in INTRADAY:
        return HistoryOut(period=period, intraday=True, interval=INTRADAY[period][1], first_date=first_date,
                          last_date=last_date, bars=_intraday(provider, security.yahoo_ticker, period),
                          sma50=[], sma200=[], rsi=[], macd=[])
    prices = all_daily_prices(db, security_id)
    closes = [p.close for p in prices]
    if period == "custom":
        low, high = start, end
    else:
        days = DAILY_WINDOW[period]
        low = prices[-1].date - timedelta(days=days) if days is not None and prices else date.min
        high = date.max
    window = [i for i, p in enumerate(prices) if low <= p.date <= high]
    interval = choose_interval(prices[window[0]].date, prices[window[-1]].date, len(window)) if window else "day"
    # Chaque groupe : indices dans `prices`. Une barre groupée porte la date de sa première séance,
    # et les indicateurs leur valeur à la dernière séance du groupe (mêmes dates que les barres).
    buckets = [[window[j] for j in g] for g in groups([prices[i].date for i in window], interval)]
    times = [prices[b[0]].date.isoformat() for b in buckets]

    def line(values: list[float | None]) -> list[LinePoint]:
        return [LinePoint(time=t, value=values[b[-1]]) for b, t in zip(buckets, times) if values[b[-1]] is not None]

    m = macd(closes)
    return HistoryOut(
        period=period, intraday=False, interval=interval, first_date=first_date, last_date=last_date,
        bars=[_merge([prices[i] for i in b], t) for b, t in zip(buckets, times)],
        sma50=line(sma(closes, 50)), sma200=line(sma(closes, 200)), rsi=line(rsi(closes)),
        macd=[MacdPoint(time=t, macd=m.macd[b[-1]], signal=m.signal[b[-1]], histogram=m.histogram[b[-1]])
              for b, t in zip(buckets, times)
              if m.macd[b[-1]] is not None and m.signal[b[-1]] is not None and m.histogram[b[-1]] is not None],
    )
```

Check the expected 5Y count in `test_history_5y_keeps_five_years` against this window (`365 * 5 + 1` days back, start day included → `365 * 5 + 2` bars on a daily series); if they disagree, fix the test's arithmetic, not the window.

`backend/app/services/assistant/tools.py`:

```python
HISTORY_DAYS = {"1M": 31, "6M": 183, "1Y": 365, "5Y": 365 * 5, "10Y": 365 * 10, "MAX": None}
```

In `_history`: error message `"Période invalide : utilisez 1M, 6M, 1Y, 5Y, 10Y ou MAX."`, and

```python
    days = HISTORY_DAYS[period]
    since = prices[-1].date - timedelta(days=days) if days is not None else prices[0].date
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_price_window.py tests/test_api_security_detail.py tests/test_assistant_tools.py`
Expected: PASS.

- [ ] **Step 5: Full backend suite, then commit**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
Expected: all pass.

```bash
git add backend
git commit -m "feat: 10Y, Max and custom chart periods with weekly or monthly grouping"
```

---

### Task 4: Simulator API — free duration and history cap

**Files:**
- Create: `backend/app/services/durations.py`
- Modify: `backend/app/api/routes/security_detail.py` (`simulate`, `simulate_since`), `backend/app/schemas/security_detail.py` (`SimulationOut`)
- Test: `backend/tests/test_durations.py` (create), `backend/tests/test_api_security_detail.py`

**Interfaces:**
- Produces: `Unit = Literal["days", "weeks", "months", "years"]`; `date_before(day: date, duration: int, unit: Unit) -> date`; `months_before(day: date, months: int) -> date`; `SimulationOut.note: str | None`; `GET /securities/{id}/simulate?amount=&duration=1..36500&unit=days|weeks|months|years` (duration wins over `period`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_durations.py`:

```python
from datetime import date

from app.services.durations import EARLIEST, date_before, months_before


def test_months_before_clamps_day_and_floor():
    assert months_before(date(2026, 3, 31), 1) == date(2026, 2, 28)
    assert months_before(date(2024, 3, 31), 1) == date(2024, 2, 29)
    assert months_before(date(2026, 1, 15), 1) == date(2025, 12, 15)
    assert months_before(date(2026, 9, 25), 36500) == EARLIEST


def test_date_before_units():
    day = date(2026, 9, 25)
    assert date_before(day, 3, "days") == date(2026, 9, 22)
    assert date_before(day, 2, "weeks") == date(2026, 9, 11)
    assert date_before(day, 6, "months") == date(2026, 3, 25)
    assert date_before(date(2024, 2, 29), 1, "years") == date(2023, 2, 28)
    assert date_before(day, 36500, "weeks") == EARLIEST
```

In `backend/tests/test_api_security_detail.py`, add `assert body["note"] is None` to `test_simulate`, and add:

```python
def test_simulate_custom_duration(client, db):
    security = with_history(db)  # clôture du jour i : 100 + i, dernier jour le 25/09
    body = client.get(f"/api/securities/{security.id}/simulate",
                      params={"amount": 1000, "duration": 2, "unit": "weeks"}).json()
    assert body["start_date"] == "2026-09-11" and body["start_price"] == 385.0
    assert body["note"] is None


def test_simulate_beyond_history_starts_at_first_close(client, db):
    security = with_history(db)
    first = LAST - timedelta(days=299)
    body = client.get(f"/api/securities/{security.id}/simulate",
                      params={"amount": 1000, "duration": 10, "unit": "years"}).json()
    assert body["start_date"] == first.isoformat() and body["start_price"] == 100.0
    assert body["note"] == f"Historique disponible depuis le {first:%d/%m/%Y} : la simulation part de cette date."


def test_simulate_rejects_invalid_duration(client, db):
    security = with_history(db)
    url = f"/api/securities/{security.id}/simulate"
    assert client.get(url, params={"amount": 500, "duration": 0, "unit": "days"}).status_code == 422
    assert client.get(url, params={"amount": 500, "duration": 2, "unit": "decades"}).status_code == 422
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_durations.py tests/test_api_security_detail.py`
Expected: FAIL — module `app.services.durations` missing; `duration` ignored (start date one month back); no `note` key.

- [ ] **Step 3: Implement**

Create `backend/app/services/durations.py`:

```python
"""Durées libres du simulateur : « il y a 2 semaines », « il y a 10 ans »."""
from calendar import monthrange
from datetime import date, timedelta
from typing import Literal

Unit = Literal["days", "weeks", "months", "years"]

EARLIEST = date(1900, 1, 1)  # plancher : aucune cotation n'est plus ancienne, et on reste dans le calendrier


def months_before(day: date, months: int) -> date:
    """Même jour, `months` mois plus tôt ; ramené au dernier jour du mois s'il n'existe pas (31/03 → 28/02)."""
    year, month = divmod(day.year * 12 + day.month - 1 - months, 12)
    if year < EARLIEST.year:
        return EARLIEST
    return date(year, month + 1, min(day.day, monthrange(year, month + 1)[1]))


def date_before(day: date, duration: int, unit: Unit) -> date:
    if unit == "days":
        return max(EARLIEST, day - timedelta(days=duration))
    if unit == "weeks":
        return max(EARLIEST, day - timedelta(weeks=duration))
    return months_before(day, duration * 12 if unit == "years" else duration)
```

`backend/app/schemas/security_detail.py`: add `note: str | None = None` after `message` in `SimulationOut`.

`backend/app/api/routes/security_detail.py` (import `Unit, date_before`):

```python
@router.get("/securities/{security_id}/simulate", response_model=SimulationOut)
def simulate(
    security_id: int,
    amount: float = Query(..., gt=0, le=1_000_000),
    period: Literal["1W", "1M", "6M", "1Y"] = "1M",
    duration: int | None = Query(None, ge=1, le=36500),
    unit: Unit = "days",
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> SimulationOut:
    """Boutons rapides (`period`) ou durée libre (`duration` + `unit`, prioritaire)."""
    prices = all_daily_prices(db, security_id)
    last = prices[-1].date if prices else date.today()
    first_day = date_before(last, duration, unit) if duration is not None else last - timedelta(days=SIMULATION_WINDOW[period])
    return simulate_since(db, user.id if user else None, security_id, amount, first_day)
```

In `simulate_since`, after `start = next(...)`:

```python
    note = None
    if first_day < prices[0].date:
        note = f"Historique disponible depuis le {prices[0].date:%d/%m/%Y} : la simulation part de cette date."
```

and pass `note=note` to both `SimulationOut(...)` returns that follow (the « ne permet pas d'acheter » one and the final one).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_durations.py tests/test_api_security_detail.py tests/test_assistant_tools.py`
Expected: PASS (the assistant's `simulate_past_investment` now also returns `note`).

- [ ] **Step 5: Full backend suite, then commit**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
Expected: all pass.

```bash
git add backend
git commit -m "feat: simulator accepts any duration and says when history starts later"
```

---

### Task 5: Chart — 10A, Max, Personnalisé

**Files:**
- Modify: `frontend/src/features/security/PriceChartPanel.tsx`, `frontend/src/lib/api/schema.d.ts` (regenerated)
- Test: `frontend/src/features/security/PriceChartPanel.test.tsx` (create)

**Interfaces:**
- Consumes: `HistoryOut.interval`, `first_date`, `last_date` (Task 3); `period=custom&start&end`.

- [ ] **Step 1: Regenerate the API types**

Run: `docker compose up -d --build api`, then in `frontend/`: `npm run gen:api`.
Expected: `schema.d.ts` gains `interval`, `first_date`, `last_date` on `HistoryOut`, `note` on `SimulationOut`, and the new query parameters. `npx tsc -b` still passes.

- [ ] **Step 2: Write the failing test**

Create `frontend/src/features/security/PriceChartPanel.test.tsx`:

```tsx
import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { PriceChartPanel } from "./PriceChartPanel";

vi.mock("./PriceChart", () => ({ PriceChart: () => <div data-testid="price-chart" /> }));
afterEach(() => vi.unstubAllGlobals());

const HISTORY = {
  period: "6M", intraday: false, interval: "day", first_date: "2000-01-03", last_date: "2026-09-25",
  bars: [{ time: "2026-09-25", open: 1, high: 1, low: 1, close: 1, volume: 1 }], sma50: [], sma200: [], rsi: [], macd: [],
};

const urls = (fetchMock: ReturnType<typeof mockFetch>) => fetchMock.mock.calls.map(([url]) => String(url));

test("périodes 10A et Max", async () => {
  const fetchMock = mockFetch(() => ({ body: HISTORY }));
  renderWithProviders(<PriceChartPanel securityId={1} />);
  await screen.findByTestId("price-chart");
  await userEvent.click(screen.getByRole("button", { name: "10A" }));
  await userEvent.click(screen.getByRole("button", { name: "Max" }));
  expect(urls(fetchMock).some((u) => u.includes("period=10Y"))).toBe(true);
  expect(urls(fetchMock).some((u) => u.includes("period=MAX"))).toBe(true);
});

test("période personnalisée bornée à l'historique", async () => {
  const fetchMock = mockFetch(() => ({ body: HISTORY }));
  renderWithProviders(<PriceChartPanel securityId={1} />);
  await screen.findByTestId("price-chart");
  await userEvent.click(screen.getByRole("button", { name: "Personnalisé" }));
  const start = screen.getByLabelText("Début");
  const end = screen.getByLabelText("Fin");
  expect(start).toHaveAttribute("min", "2000-01-03");
  expect(end).toHaveAttribute("max", "2026-09-25");
  fireEvent.change(start, { target: { value: "2020-01-01" } });
  fireEvent.change(end, { target: { value: "2019-01-01" } });
  expect(screen.getByText("La date de fin doit suivre la date de début.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Appliquer" })).toBeDisabled();
  fireEvent.change(end, { target: { value: "2021-06-30" } });
  await userEvent.click(screen.getByRole("button", { name: "Appliquer" }));
  expect(urls(fetchMock).some((u) => u.includes("period=custom") && u.includes("start=2020-01-01") && u.includes("end=2021-06-30"))).toBe(true);
});

test("indique le regroupement des barres", async () => {
  mockFetch(() => ({ body: { ...HISTORY, interval: "month" } }));
  renderWithProviders(<PriceChartPanel securityId={1} />);
  expect(await screen.findByText("Une barre par mois sur cette période.")).toBeInTheDocument();
});
```

Run: `npx vitest run src/features/security/PriceChartPanel.test.tsx`
Expected: FAIL — no « 10A » button.

- [ ] **Step 3: Implement**

`frontend/src/features/security/PriceChartPanel.tsx` (add `keepPreviousData` to the TanStack import and `Input` from `@/components/ui/input`):

```tsx
const PERIODS = [
  { value: "1D", label: "1J" }, { value: "1W", label: "1S" }, { value: "1M", label: "1M" },
  { value: "6M", label: "6M" }, { value: "1Y", label: "1A" }, { value: "5Y", label: "5A" },
  { value: "10Y", label: "10A" }, { value: "MAX", label: "Max" }, { value: "custom", label: "Personnalisé" },
] as const;
type Period = (typeof PERIODS)[number]["value"];
const GROUPED: Record<string, string> = {
  week: "Une barre par semaine sur cette période.", month: "Une barre par mois sur cette période.",
};

export function PriceChartPanel({ securityId }: { securityId: number }) {
  const [period, setPeriod] = useState<Period>("6M");
  const [draft, setDraft] = useState({ start: "", end: "" });
  const [range, setRange] = useState<{ start: string; end: string } | null>(null);
  const [toggles, setToggles] = useState({ sma50: true, sma200: true, rsi: false, macd: false });
  const custom = period === "custom";
  const { data, isPending, isError } = useQuery({
    queryKey: ["history", securityId, period, custom ? range : null],
    queryFn: () => apiGet<HistoryOut>(`/api/securities/${securityId}/history`, custom ? { period, ...range } : { period }),
    enabled: !custom || range !== null,
    placeholderData: keepPreviousData,  // en « Personnalisé », la période précédente reste affichée en attendant les dates
    refetchInterval: period === "1D" ? 60_000 : false,
  });
  const reversed = draft.start !== "" && draft.end !== "" && draft.end < draft.start;
  const choose = (value: Period) => {
    if (value === "custom" && !custom) setDraft({ start: data?.first_date ?? "", end: data?.last_date ?? "" });
    setPeriod(value);
  };
  // … `intraday` and `toggle` unchanged …
```

In the JSX: the period button row becomes `<div className="flex flex-wrap gap-1">` and each button calls `choose(p.value)`. Right after the row containing the buttons and toggles, add:

```tsx
        {custom && (
          <form className="flex flex-wrap items-center gap-2 text-sm"
                onSubmit={(e) => { e.preventDefault(); if (!reversed && draft.start && draft.end) setRange({ ...draft }); }}>
            <label className="flex items-center gap-1.5">Du
              <Input type="date" aria-label="Début" className="w-40 bg-white" value={draft.start}
                     min={data?.first_date ?? undefined} max={data?.last_date ?? undefined}
                     onChange={(e) => setDraft({ ...draft, start: e.target.value })} />
            </label>
            <label className="flex items-center gap-1.5">au
              <Input type="date" aria-label="Fin" className="w-40 bg-white" value={draft.end}
                     min={data?.first_date ?? undefined} max={data?.last_date ?? undefined}
                     onChange={(e) => setDraft({ ...draft, end: e.target.value })} />
            </label>
            <Button type="submit" size="sm" disabled={reversed || !draft.start || !draft.end}>Appliquer</Button>
            {reversed && <p role="alert" className="w-full text-down">La date de fin doit suivre la date de début.</p>}
          </form>
        )}
```

After the chart (inside the final branch of the ternary, below `<PriceChart …/>`, wrapped in a fragment), add:

```tsx
            {GROUPED[data.interval] && <p className="text-xs text-muted-foreground">{GROUPED[data.interval]}</p>}
```

If `keepPreviousData` does not keep the previous data while the custom query is disabled (the bounds test fails with no `min` attribute), keep the last loaded bounds in a `useState` updated from `data` instead, and ledger the ruling.

- [ ] **Step 4: Run the tests to verify they pass**

Run (in `frontend/`): `npx vitest run src/features/security/PriceChartPanel.test.tsx`, then `npx tsc -b`, `npx vitest run`, `npx oxlint`
Expected: PASS, no type errors, no lint errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat: 10A, Max and custom date range on the security chart"
```

---

### Task 6: Simulator — « Autre durée »

**Files:**
- Modify: `frontend/src/features/security/SimulatorCard.tsx`
- Test: `frontend/src/features/security/SimulatorCard.test.tsx` (create)

**Interfaces:**
- Consumes: `simulate?duration=&unit=` and `SimulationOut.note` (Task 4).

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/security/SimulatorCard.test.tsx`:

```tsx
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { SimulatorCard } from "./SimulatorCard";

afterEach(() => vi.unstubAllGlobals());

const NOTE = "Historique disponible depuis le 03/01/2000 : la simulation part de cette date.";
const SIMULATION = { start_date: "2000-01-03", start_price: 10, current_price: 40, shares: 50, invested: 500, buy_fee: 2.4,
                     sell_fee: 3.6, current_value: 2000, gain: 1494, gain_pct: 297.9, message: null, note: NOTE };

function setup() {
  return mockFetch((url) => url.startsWith("/api/fees") ? { body: { amount: 500, fee: 2.4, rate: 0.0048 } } : { body: SIMULATION });
}

const simulateUrls = (fetchMock: ReturnType<typeof mockFetch>) =>
  fetchMock.mock.calls.map(([url]) => String(url)).filter((u) => u.includes("/simulate"));

test("autre durée : nombre et unité, puis note sur l'historique", async () => {
  const fetchMock = setup();
  renderWithProviders(<SimulatorCard securityId={1} />);
  await userEvent.selectOptions(screen.getByLabelText("Période"), "other");
  await userEvent.clear(screen.getByLabelText("Durée"));
  await userEvent.type(screen.getByLabelText("Durée"), "10");
  await userEvent.selectOptions(screen.getByLabelText("Unité"), "years");
  await userEvent.click(screen.getByRole("button", { name: "Simuler" }));
  expect(await screen.findByText(NOTE)).toBeInTheDocument();
  const [url] = simulateUrls(fetchMock);
  expect(url).toContain("duration=10");
  expect(url).toContain("unit=years");
  expect(url).not.toContain("period=");
});

test("durée invalide : aucune simulation", async () => {
  const fetchMock = setup();
  renderWithProviders(<SimulatorCard securityId={1} />);
  await userEvent.selectOptions(screen.getByLabelText("Période"), "other");
  await userEvent.clear(screen.getByLabelText("Durée"));
  await userEvent.type(screen.getByLabelText("Durée"), "0");
  await userEvent.click(screen.getByRole("button", { name: "Simuler" }));
  expect(simulateUrls(fetchMock)).toEqual([]);
});
```

Run: `npx vitest run src/features/security/SimulatorCard.test.tsx`
Expected: FAIL — no « other » option.

- [ ] **Step 2: Implement**

`frontend/src/features/security/SimulatorCard.tsx`:

```tsx
const PERIODS = [
  { value: "1W", label: "1 semaine" }, { value: "1M", label: "1 mois" }, { value: "6M", label: "6 mois" },
  { value: "1Y", label: "1 an" }, { value: "other", label: "Autre durée" },
];
const UNITS = [{ value: "days", label: "jours" }, { value: "weeks", label: "semaines" }, { value: "months", label: "mois" }, { value: "years", label: "ans" }];
const MAX_DURATION = 36500;  // même plafond que l'API
type SimulationRequest = { amount: number; period: string } | { amount: number; duration: number; unit: string };
```

In the component: `const [duration, setDuration] = useState("2");`, `const [unit, setUnit] = useState("years");`, `const [request, setRequest] = useState<SimulationRequest | null>(null);`, and the form's submit handler:

```tsx
onSubmit={(e) => {
  e.preventDefault();
  if (!(value > 0)) return;
  if (period !== "other") { setRequest({ amount: value, period }); return; }
  const count = Number(duration);
  if (Number.isInteger(count) && count >= 1 && count <= MAX_DURATION) setRequest({ amount: value, duration: count, unit });
}}
```

After the « Période » select, inside the form:

```tsx
          {period === "other" && (
            <>
              <Input aria-label="Durée" inputMode="numeric" className="w-16 bg-white" value={duration} onChange={(e) => setDuration(e.target.value)} />
              <select aria-label="Unité" value={unit} onChange={(e) => setUnit(e.target.value)} className="h-8 rounded-lg border border-input bg-white px-2">
                {UNITS.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
              </select>
            </>
          )}
```

Just before `{result && (result.message ? …`, add:

```tsx
        {result?.note && <p className="text-muted-foreground">{result.note}</p>}
```

- [ ] **Step 3: Run the tests to verify they pass**

Run (in `frontend/`): `npx vitest run src/features/security`, then `npx tsc -b`, `npx vitest run`, `npx oxlint`
Expected: PASS (the existing « simulateur et aide sur les frais » test in `SecurityPage.test.tsx` still passes: quick buttons unchanged).

- [ ] **Step 4: Commit**

```bash
git add frontend/src
git commit -m "feat: simulator Autre durée with a number and a unit"
```

---

### Task 7: Docs, e2e and local backfill check

**Files:**
- Modify: `frontend/public/guide/app/fiche-titre.md`, `frontend/public/guide/premiers-pas.md`, `frontend/public/guide/bourse/risques.md`
- Modify: `frontend/public/documentation/api.md`, `donnees.md`, `base-de-donnees.md`, `installation.md`, `architecture.md`, `assistant.md`
- Modify: `README.md` (line 22), `CLAUDE.md` if it lists the scheduled jobs (line 33)
- Test: `frontend/src/docs.test.ts` (existing guard), e2e

- [ ] **Step 1: Update the user guide**

`guide/app/fiche-titre.md`, « Graphique » table, replace the `1M, 6M, 1A, 5A` row with:

```markdown
| 1M, 6M, 1A, 5A | Une journée |
| 10A | Une journée, ou une semaine quand il y a trop de séances à afficher |
| Max | Tout l'historique depuis la première cotation : une journée, une semaine ou un mois selon sa longueur |
| Personnalisé | Choisissez une date de début et une date de fin, puis cliquez sur **Appliquer** |
```

and add under the table: `Quand les bougies sont regroupées, une ligne sous le graphique le précise (« Une barre par semaine sur cette période »).`

In the « Cartes » table, the **Simulateur** row becomes:

```markdown
| **Simulateur** | « Si j'avais investi X € il y a 1 semaine / 1 mois / 6 mois / 1 an », ou **Autre durée** (par exemple 2 semaines, 5 ans, 10 ans) : gain en euros et en %, frais compris. Si le titre est coté depuis moins longtemps, la simulation part de sa première cotation et le dit. |
```

`guide/premiers-pas.md` line 27: `- le **graphique** sur 1 an, 5 ans ou plus (jusqu'à la première cotation) : l'action monte-t-elle régulièrement, ou fait-elle les montagnes russes ?`
`guide/bourse/risques.md` line 66: `- [ ] J'ai regardé le graphique sur 1 an, 5 ans et plus.`

- [ ] **Step 2: Update the admin documentation**

- `documentation/api.md` line 103: `| GET | \`/securities/{id}/history?period=1D\|1W\|1M\|6M\|1Y\|5Y\|10Y\|MAX\|custom\` | Barres OHLCV, MM50/MM200, RSI, MACD, et bornes de l'historique stocké (\`first_date\`, \`last_date\`). \`1D\` (barres de 5 min) et \`1W\` (30 min) sont en intraday, chargés depuis Yahoo et mis en cache. \`custom\` exige \`start\` et \`end\` (fin ≥ début, sinon 422). Au-delà de 2 500 séances, les barres sont regroupées par semaine (jusqu'à 10 ans) ou par mois (\`interval\`) |`
- `documentation/api.md` line 106: `| GET | \`/securities/{id}/simulate?amount=&period=1W\|1M\|6M\|1Y\` ou \`&duration=&unit=days\|weeks\|months\|years\` | « Si j'avais investi », frais inclus. La durée libre (1 à 36 500) l'emporte sur \`period\` ; si l'historique commence plus tard, la simulation part de la première cotation et \`note\` le dit |`
- `documentation/donnees.md`: add to the jobs table, after `evening`: `| \`history_backfill\` | 20 h 00 tous les jours, et à la fin de \`bootstrap\` | Rattrapage de l'historique complet : charge, pour chaque titre pas encore marqué \`history_complete\`, les cours antérieurs à sa première date stockée. Par paquets de 100 titres ; ne fait plus rien une fois tout rattrapé |`; in « Détails », add `historique complet` to the heavy jobs list, and replace the line « L'historique est conservé sur **5 ans**… » with: `L'historique est **complet** : un nouveau titre est chargé depuis sa première cotation, les titres déjà présents sont rattrapés par \`history_backfill\`. Si Yahoo a réajusté les anciens cours (division, dividende), toute la série du titre est rechargée. Les statistiques des prévisions ne lisent que les 5 dernières années.`
- `documentation/base-de-donnees.md` line 17: append `, historique complet chargé (\`history_complete\`)` before `| non |`; line 20: `| \`daily_prices\` | Historique journalier OHLCV depuis la première cotation | non |`. If the page gives a size estimate for `daily_prices`, say it grows about ×3 to ×5 with the full history.
- `documentation/installation.md`, worker table: replace the history row with `| Historique de cours des 5 dernières années… puis de tout l'historique (rattrapage en arrière-plan) | une dizaine de minutes, puis environ une demi-heure |`. Read the surrounding text first and keep it consistent.
- `documentation/architecture.md` line 132: delete the `HISTORY_YEARS` row.
- `documentation/assistant.md` line 28: `| \`get_price_history\` | Clôtures et indicateurs sur une période (1M, 6M, 1Y, 5Y, 10Y ou MAX) |`
- `README.md` line 22: replace `5 ans d'historique` with `tout l'historique` and adjust the wait sentence if needed. `CLAUDE.md` line 33: add the `history_backfill` job at 20 h if the line lists the scheduled jobs.

After a new security is loaded, `bootstrap`'s first `daily_history` call loads **everything** for securities without prices, so the « 5 dernières années… puis » wording in `installation.md` is only right for an upgraded install; for a fresh install the first load is already complete. Write the row to match what the code does: first load = full history for all securities (longer: say « environ une demi-heure »).

- [ ] **Step 3: Run the doc and unit checks**

Run (in `frontend/`): `npx vitest run src/docs.test.ts` and `npx vitest run`
Expected: PASS.

- [ ] **Step 4: e2e**

Run: `docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --build api worker web`, then in `frontend/`: `npm run e2e`.
Expected: all pass (layout spec clicks « Simuler » on a security page at each width; the 9 period buttons must wrap without clipping). Then restore: `docker compose up -d --build api worker web`.

- [ ] **Step 5: Local backfill check (dev stack)**

After the restore, the migration runs on the dev DB and the worker's bootstrap ends with `history_backfill`. Do not wait for it to finish. Check progress and size with:

```bash
docker compose exec -T db psql -U pea -d pea_radar -c "SELECT history_complete, count(*) FROM securities WHERE active GROUP BY 1;" -c "SELECT pg_size_pretty(pg_total_relation_size('daily_prices'));"
```

Record the numbers (before/after if the run finishes during the session) for the PR description. If the worker log shows Yahoo throttling (many empty responses), ledger it; do not change the batch size without a ruling.

- [ ] **Step 6: Commit**

```bash
git add frontend/public README.md CLAUDE.md
git commit -m "docs: full history, chart periods and free simulator duration"
```
