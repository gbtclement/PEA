from apscheduler.schedulers.base import BaseScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import func, select

from app.jobs.context import JobContext
from app.jobs.market import refresh_daily_history, refresh_fundamentals, refresh_quotes
from app.jobs.runner import run_job
from app.jobs.universe import refresh_universe
from app.models import DailyPrice, Security, SecurityFundamentals
from app.services.market_calendar import is_market_open


def _refresh_tier(ctx: JobContext, tier: int) -> None:
    run_job(ctx, f"quotes_t{tier}", lambda c: refresh_quotes(c, tier))


def quotes_job(ctx: JobContext, tier: int) -> None:
    if is_market_open(ctx.now()):
        _refresh_tier(ctx, tier)


def daily_job(ctx: JobContext) -> None:
    run_job(ctx, "daily_history", refresh_daily_history)
    run_job(ctx, "fundamentals", refresh_fundamentals)


def bootstrap_job(ctx: JobContext) -> None:
    """Au démarrage : remplit ce qui manque, puis charge les cours même hors séance."""
    with ctx.session_factory() as session:
        has_securities = session.scalar(select(func.count(Security.id))) > 0
        has_prices = session.scalar(select(func.count()).select_from(DailyPrice)) > 0
        has_fundamentals = session.scalar(select(func.count()).select_from(SecurityFundamentals)) > 0
    if not has_securities:
        run_job(ctx, "universe", refresh_universe)
    if not has_prices:
        run_job(ctx, "daily_history", refresh_daily_history)
    for tier in (1, 2, 3):
        _refresh_tier(ctx, tier)
    if not has_fundamentals:
        run_job(ctx, "fundamentals", refresh_fundamentals)


def build_scheduler(ctx: JobContext, scheduler: BaseScheduler | None = None) -> BaseScheduler:
    tz = ctx.settings.timezone
    scheduler = scheduler or BlockingScheduler(timezone=tz)
    common = {"max_instances": 1, "coalesce": True, "misfire_grace_time": 300}
    scheduler.add_job(bootstrap_job, "date", args=[ctx], id="bootstrap", **common)
    scheduler.add_job(run_job, CronTrigger(day_of_week="mon-fri", hour=7, minute=0, timezone=tz),
                      args=[ctx, "universe", refresh_universe], id="universe", **common)
    scheduler.add_job(daily_job, CronTrigger(day_of_week="mon-fri", hour=7, minute=30, timezone=tz),
                      args=[ctx], id="daily", **common)
    intervals = {1: ctx.settings.quotes_t1_minutes, 2: ctx.settings.quotes_t2_minutes, 3: ctx.settings.quotes_t3_minutes}
    for tier, minutes in intervals.items():
        scheduler.add_job(quotes_job, IntervalTrigger(minutes=minutes, timezone=tz), args=[ctx, tier],
                          id=f"quotes_t{tier}", **common)
    return scheduler
