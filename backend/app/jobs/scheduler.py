import logging
import threading
from datetime import datetime, timedelta

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.jobs.context import JobContext
from app.jobs.privacy import build_pending_exports
from app.jobs.forecasts import refresh_forecast_stats, refresh_forecasts, stats_are_stale
from app.jobs.cleanup import purge_security_data
from app.jobs.mail import send_pending_emails
from app.jobs.notifications import run_price_alerts
from app.jobs.market import refresh_daily_history, refresh_fundamentals, refresh_quotes
from app.jobs.runner import run_job
from app.jobs.scoring import refresh_scores
from app.jobs.universe import refresh_universe
from app.models import DailyPrice, DataStatus, Security, SecurityFundamentals
from app.services.market_calendar import is_market_open, last_session_close

# Univers, historique et fondamentaux s'exécutent l'un après l'autre (charge Yahoo, conflits d'insertion).
HEAVY_JOBS_LOCK = threading.Lock()
_DAILY_MAX_AGE = timedelta(hours=20)  # « une fois par jour », même si la veille le PC a démarré plus tard


def _refresh_tier(ctx: JobContext, tier: int) -> None:
    run_job(ctx, f"quotes_t{tier}", lambda c: refresh_quotes(c, tier))


def _refresh_scores(ctx: JobContext) -> None:
    run_job(ctx, "scores", refresh_scores)


def _quietly(ctx: JobContext, fn) -> None:
    """Notifications : une panne est journalisée, sans bloquer la tâche qui les déclenche."""
    try:
        fn(ctx)
    except Exception:
        logging.getLogger(__name__).exception("Échec d'une tâche de notification (%s)", fn.__name__)


def quotes_job(ctx: JobContext, tier: int) -> None:
    if is_market_open(ctx.now()):
        _refresh_tier(ctx, tier)
        _quietly(ctx, run_price_alerts)  # N2 : après chaque mise à jour des cours
        if tier == 2:
            _refresh_scores(ctx)


def universe_job(ctx: JobContext) -> None:
    with HEAVY_JOBS_LOCK:
        run_job(ctx, "universe", refresh_universe)


def daily_job(ctx: JobContext) -> None:
    with HEAVY_JOBS_LOCK:
        run_job(ctx, "daily_history", refresh_daily_history)
        _refresh_scores(ctx)
        _refresh_forecasts(ctx)
        run_job(ctx, "fundamentals", refresh_fundamentals)


def evening_job(ctx: JobContext) -> None:
    """Après la clôture : cours de clôture officiels du jour, puis scores et prévisions (soirée et week-end exacts)."""
    with HEAVY_JOBS_LOCK:
        run_job(ctx, "daily_history", refresh_daily_history)
        _refresh_scores(ctx)
        _refresh_forecasts(ctx)


def _refresh_forecasts(ctx: JobContext) -> None:
    """Statistiques des signaux une fois par semaine, prédictions du jour à chaque passage."""
    if stats_are_stale(ctx):
        run_job(ctx, "forecast_stats", refresh_forecast_stats)
    run_job(ctx, "forecasts", refresh_forecasts)


def _last_success(session: Session, job: str) -> datetime | None:
    status = session.get(DataStatus, job)
    return status.last_success_at if status else None


def _older_than(last: datetime | None, threshold: datetime) -> bool:
    return last is None or last < threshold


def bootstrap_job(ctx: JobContext) -> None:
    """Au démarrage : rattrape ce qui manque ou a vieilli (PC éteint à 7h), puis charge les cours."""
    now = ctx.now()
    with ctx.session_factory() as session:
        has_securities = session.scalar(select(func.count(Security.id))) > 0
        has_prices = session.scalar(select(func.count()).select_from(DailyPrice)) > 0
        has_fundamentals = session.scalar(select(func.count()).select_from(SecurityFundamentals)) > 0
        universe_at = _last_success(session, "universe")
        history_at = _last_success(session, "daily_history")
        fundamentals_at = _last_success(session, "fundamentals")
        forecasts_at = _last_success(session, "forecasts")
    with HEAVY_JOBS_LOCK:
        if not has_securities or _older_than(universe_at, now - _DAILY_MAX_AGE):
            run_job(ctx, "universe", refresh_universe)
        if not has_prices or _older_than(history_at, last_session_close(now)):
            run_job(ctx, "daily_history", refresh_daily_history)
        if _older_than(forecasts_at, last_session_close(now)):
            _refresh_forecasts(ctx)
    for tier in (1, 2, 3):
        _refresh_tier(ctx, tier)
    _refresh_scores(ctx)
    with HEAVY_JOBS_LOCK:
        if not has_fundamentals or _older_than(fundamentals_at, now - _DAILY_MAX_AGE):
            run_job(ctx, "fundamentals", refresh_fundamentals)
            # Sans fondamentaux, aucune action n'atteint le taux de données exigé pour le top 10
            _refresh_scores(ctx)


def mail_job(ctx: JobContext) -> None:
    # Toutes les 5 s : pas de trace dans data_status (run_job) pour ne pas noyer le suivi des données.
    try:
        send_pending_emails(ctx)
    except Exception:
        logging.getLogger(__name__).exception("Échec de la file d'envoi des mails")


def exports_job(ctx: JobContext) -> None:
    # Toutes les 15 s, comme la file des mails : pas de trace dans data_status.
    try:
        build_pending_exports(ctx)
    except Exception:
        logging.getLogger(__name__).exception("Échec de la préparation des exports")


def cleanup_job(ctx: JobContext) -> None:
    run_job(ctx, "cleanup", purge_security_data)


def build_scheduler(ctx: JobContext, scheduler: BaseScheduler | None = None) -> BaseScheduler:
    tz = ctx.settings.timezone
    scheduler = scheduler or BlockingScheduler(timezone=tz)
    common = {"max_instances": 1, "coalesce": True, "misfire_grace_time": 300}
    daily = {**common, "misfire_grace_time": 3 * 3600}  # rattrapées si le PC sort de veille dans les 3 h
    scheduler.add_job(bootstrap_job, "date", args=[ctx], id="bootstrap", **common)
    scheduler.add_job(universe_job, CronTrigger(day_of_week="mon-fri", hour=7, minute=0, timezone=tz),
                      args=[ctx], id="universe", **daily)
    scheduler.add_job(daily_job, CronTrigger(day_of_week="mon-fri", hour=7, minute=30, timezone=tz),
                      args=[ctx], id="daily", **daily)
    scheduler.add_job(evening_job, CronTrigger(day_of_week="mon-fri", hour=18, minute=15, timezone=tz),
                      args=[ctx], id="evening", **daily)
    scheduler.add_job(cleanup_job, CronTrigger(hour=3, minute=30, timezone=tz), args=[ctx], id="cleanup", **daily)
    intervals = {1: ctx.settings.quotes_t1_minutes, 2: ctx.settings.quotes_t2_minutes, 3: ctx.settings.quotes_t3_minutes}
    for tier, minutes in intervals.items():
        scheduler.add_job(quotes_job, IntervalTrigger(minutes=minutes, timezone=tz), args=[ctx, tier],
                          id=f"quotes_t{tier}", **common)
    scheduler.add_job(exports_job, IntervalTrigger(seconds=15, timezone=tz), args=[ctx], id="exports", **common)
    if ctx.mailer is not None:
        scheduler.add_job(mail_job, IntervalTrigger(seconds=5, timezone=tz), args=[ctx], id="emails", **common)
    else:
        logging.getLogger(__name__).warning("SMTP_HOST vide : les mails restent en file d'attente.")
    return scheduler
