from datetime import UTC, date, datetime

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func, select

from app.jobs.scheduler import bootstrap_job, build_scheduler, quotes_job
from app.models import Security
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
