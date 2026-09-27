from datetime import UTC, date, datetime

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func, select

from app.jobs.scheduler import bootstrap_job, build_scheduler, quotes_job
from app.models import DataStatus, ForecastRun, Security
from app.providers.base import DailyBar, ListedSecurity, Quote
from tests.factories import make_security
from tests.fakes import FakeListing, FakeMarket

OPEN_MONDAY = datetime(2026, 9, 28, 8, 0, tzinfo=UTC)      # 10h00 à Paris
GOOD_FRIDAY = datetime(2026, 4, 3, 8, 0, tzinfo=UTC)
BEFORE_OPEN = datetime(2026, 9, 28, 6, 0, tzinfo=UTC)      # 8h00 à Paris


def index_ctx(db, make_ctx, now):
    make_security(db, "^FCHI", kind="index", eligibility="non_eligible", country=None)
    market = FakeMarket(quotes={"^FCHI": Quote(7500.0, 7450.0, 0.67, None, now)})
    return make_ctx(market=market, now=now), market


def test_quotes_job_runs_when_open(db, make_ctx):
    ctx, market = index_ctx(db, make_ctx, OPEN_MONDAY)
    quotes_job(ctx, 1)
    assert market.quote_calls == [["^FCHI"]]


def test_quotes_job_skips_holiday(db, make_ctx):
    ctx, market = index_ctx(db, make_ctx, GOOD_FRIDAY)
    quotes_job(ctx, 1)
    assert market.quote_calls == []


def test_quotes_job_skips_before_open(db, make_ctx):
    ctx, market = index_ctx(db, make_ctx, BEFORE_OPEN)
    quotes_job(ctx, 1)
    assert market.quote_calls == []


def test_build_scheduler_registers_jobs(make_ctx):
    scheduler = build_scheduler(make_ctx(), BackgroundScheduler(timezone="Europe/Paris"))
    assert {job.id for job in scheduler.get_jobs()} == {
        "bootstrap", "universe", "daily", "quotes_t1", "quotes_t2", "quotes_t3",
    }


def test_bootstrap_fills_empty_database_once(db, make_ctx):
    listing = FakeListing([ListedSecurity("FR0000121014", "MC", "LVMH", "Euronext Paris", "MC.PA")])
    market = FakeMarket(
        quotes={"MC.PA": Quote(612.0, 600.0, 2.0, 10, OPEN_MONDAY)},
        history={"MC.PA": [DailyBar(date(2026, 9, 25), 600, 615, 598, 612.0, 10)]},
    )
    ctx = make_ctx(market=market, listing=listing, now=OPEN_MONDAY)
    bootstrap_job(ctx)
    assert listing.calls == 1
    assert db.scalar(select(func.count(Security.id))) > 1
    assert market.history_calls and market.quote_calls and market.fundamental_calls
    bootstrap_job(ctx)
    assert listing.calls == 1  # univers déjà présent : pas de nouveau téléchargement


def seeded_ctx(db, make_ctx, now, statuses: dict[str, datetime]):
    from app.models import DailyPrice, SecurityFundamentals
    from app.repositories.data_status import record_success

    security = make_security(db, "MC.PA")
    db.add(DailyPrice(security_id=security.id, date=date(2026, 9, 25), open=1, high=1, low=1, close=1.0, volume=1))
    db.add(SecurityFundamentals(security_id=security.id, pe=10.0))
    for job, at in statuses.items():
        record_success(db, job, 1, at)
    db.flush()
    listing = FakeListing([ListedSecurity("FR0000121014", "MC", "LVMH", "Euronext Paris", "MC.PA")])
    market = FakeMarket(quotes={"MC.PA": Quote(612.0, 600.0, 2.0, 10, now)})
    return make_ctx(market=market, listing=listing, now=now), market, listing


def test_bootstrap_refreshes_stale_data(db, make_ctx):
    # PC allumé mardi 9h ; dernières mises à jour lundi 9h05 : la clôture de lundi manque.
    tuesday = datetime(2026, 9, 29, 7, 0, tzinfo=UTC)
    monday_morning = datetime(2026, 9, 28, 7, 5, tzinfo=UTC)
    ctx, market, listing = seeded_ctx(db, make_ctx, tuesday, {
        "universe": monday_morning, "daily_history": monday_morning, "fundamentals": monday_morning,
    })
    bootstrap_job(ctx)
    assert listing.calls == 1
    assert market.history_calls
    assert market.fundamental_calls


def test_bootstrap_skips_fresh_data(db, make_ctx):
    tuesday = datetime(2026, 9, 29, 7, 0, tzinfo=UTC)
    monday_evening = datetime(2026, 9, 28, 20, 0, tzinfo=UTC)
    ctx, market, listing = seeded_ctx(db, make_ctx, tuesday, {
        "universe": monday_evening, "daily_history": monday_evening, "fundamentals": monday_evening,
    })
    bootstrap_job(ctx)
    assert listing.calls == 0
    assert market.history_calls == []
    assert market.fundamental_calls == []


def test_heavy_jobs_are_serialized(db, make_ctx):
    import threading
    import time as pytime

    from app.jobs.scheduler import HEAVY_JOBS_LOCK, daily_job

    make_security(db, "MC.PA")
    market = FakeMarket()
    ctx = make_ctx(market=market, now=OPEN_MONDAY)
    HEAVY_JOBS_LOCK.acquire()
    try:
        worker = threading.Thread(target=daily_job, args=[ctx])
        worker.start()
        pytime.sleep(0.2)
        assert market.history_calls == []  # attend la fin de la tâche lourde en cours
    finally:
        HEAVY_JOBS_LOCK.release()
    worker.join(timeout=5)
    assert market.history_calls


def test_daily_job_computes_forecasts(db, make_ctx):
    from app.jobs.scheduler import daily_job

    ctx, _, _ = seeded_ctx(db, make_ctx, datetime(2026, 9, 29, 5, 30, tzinfo=UTC), {})
    daily_job(ctx)
    for job in ("forecast_stats", "forecasts"):
        status = db.get(DataStatus, job)
        assert status is not None and status.last_success_at is not None, job
    daily_job(ctx)  # statistiques de moins de 7 jours : pas recalculées
    assert db.scalar(select(func.count()).select_from(ForecastRun)) == 1


def test_bootstrap_computes_missing_forecasts(db, make_ctx):
    ctx, _, _ = seeded_ctx(db, make_ctx, datetime(2026, 9, 29, 7, 0, tzinfo=UTC), {
        "universe": datetime(2026, 9, 28, 20, 0, tzinfo=UTC), "daily_history": datetime(2026, 9, 28, 20, 0, tzinfo=UTC),
        "fundamentals": datetime(2026, 9, 28, 20, 0, tzinfo=UTC),
    })
    bootstrap_job(ctx)
    assert db.get(DataStatus, "forecasts").last_success_at is not None
