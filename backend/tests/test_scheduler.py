from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func, select

import app.jobs.scheduler as scheduler_module
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
        "bootstrap", "universe", "daily", "evening", "quotes_t1", "quotes_t2", "quotes_t3", "cleanup", "exports",
        "price_moves", "daily_recap", "order_reminders", "weekly_recap", "billing_sync", "renewal_notices",
        "stripe_cancellations",
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


def record_jobs(monkeypatch) -> list[str]:
    import app.jobs.scheduler as scheduler

    names: list[str] = []
    real = scheduler.run_job

    def spy(ctx, name, fn):
        names.append(name)
        return real(ctx, name, fn)

    monkeypatch.setattr(scheduler, "run_job", spy)
    return names


def test_bootstrap_recomputes_scores_once_fundamentals_are_loaded(db, make_ctx, monkeypatch):
    # Premier démarrage : sans fondamentaux, aucune action n'atteint 60 % du score → top 10 vide jusqu'au lendemain.
    names = record_jobs(monkeypatch)
    listing = FakeListing([ListedSecurity("FR0000121014", "MC", "LVMH", "Euronext Paris", "MC.PA")])
    market = FakeMarket(
        quotes={"MC.PA": Quote(612.0, 600.0, 2.0, 10, OPEN_MONDAY)},
        history={"MC.PA": [DailyBar(date(2026, 9, 25), 600, 615, 598, 612.0, 10)]},
    )
    bootstrap_job(make_ctx(market=market, listing=listing, now=OPEN_MONDAY))
    assert "fundamentals" in names
    assert names[-1] == "scores"


def test_bootstrap_does_not_rescore_when_fundamentals_are_fresh(db, make_ctx, monkeypatch):
    names = record_jobs(monkeypatch)
    tuesday = datetime(2026, 9, 29, 7, 0, tzinfo=UTC)
    monday_evening = datetime(2026, 9, 28, 20, 0, tzinfo=UTC)
    ctx, _, _ = seeded_ctx(db, make_ctx, tuesday, {
        "universe": monday_evening, "daily_history": monday_evening, "fundamentals": monday_evening,
        "forecasts": monday_evening,
    })
    bootstrap_job(ctx)
    assert names.count("scores") == 1


def test_evening_job_loads_closes_then_scores_and_forecasts(db, make_ctx, monkeypatch):
    from app.jobs.scheduler import evening_job

    names = record_jobs(monkeypatch)
    ctx, market, listing = seeded_ctx(db, make_ctx, datetime(2026, 9, 28, 16, 15, tzinfo=UTC), {})  # lundi 18h15
    evening_job(ctx)
    assert names[:2] == ["daily_history", "scores"]
    assert "forecasts" in names
    assert "fundamentals" not in names and "universe" not in names
    assert market.history_calls


def test_evening_job_runs_after_the_close_on_weekdays(make_ctx):
    scheduler = build_scheduler(make_ctx(), BackgroundScheduler(timezone="Europe/Paris"))
    trigger = str(scheduler.get_job("evening").trigger)
    assert "day_of_week='mon-fri'" in trigger and "hour='18'" in trigger and "minute='15'" in trigger


def test_scheduler_sends_emails_only_with_a_mailer(make_ctx):
    from tests.fake_mailer import FakeMailer

    scheduler = build_scheduler(make_ctx(mailer=FakeMailer()), BackgroundScheduler(timezone="Europe/Paris"))
    job = scheduler.get_job("emails")
    assert job is not None and job.trigger.interval.total_seconds() == 5


def test_quotes_job_checks_price_alerts(make_ctx, monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler_module, "_refresh_tier", lambda ctx, tier: None)
    monkeypatch.setattr(scheduler_module, "_refresh_scores", lambda ctx: None)
    monkeypatch.setattr(scheduler_module, "run_price_alerts", lambda ctx: calls.append(ctx) or 0)
    scheduler_module.quotes_job(make_ctx(now=datetime(2026, 9, 29, 10, 0, tzinfo=ZoneInfo("Europe/Paris"))), 1)
    assert len(calls) == 1


def test_evening_job_snapshots_scores_then_notifies(make_ctx, monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler_module, "run_job", lambda ctx, name, fn: calls.append(name))
    monkeypatch.setattr(scheduler_module, "_refresh_forecasts", lambda ctx: calls.append("forecasts"))
    monkeypatch.setattr(scheduler_module, "run_score_notifications", lambda ctx: calls.append("score_notifications"))
    scheduler_module.evening_job(make_ctx())
    assert calls[-1] == "score_notifications"
