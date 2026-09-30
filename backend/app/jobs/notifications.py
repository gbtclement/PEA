"""Tâches du worker qui envoient les notifications N1 à N6 (spec 5.1)."""
from app.jobs.context import JobContext
from app.services.market_calendar import PARIS, is_market_open
from app.services.notifications.moves import notify_price_moves
from app.services.notifications.price_alerts import check_price_alerts
from app.services.notifications.recaps import send_daily_recaps, send_weekly_recaps
from app.services.notifications.reminders import send_order_reminders
from app.services.notifications.scores import notify_score_changes, take_score_snapshot
from app.services.notifications.send import notifications_ready


def run_price_alerts(ctx: JobContext) -> int:
    if not notifications_ready():
        return 0
    with ctx.session_factory() as db:
        sent = check_price_alerts(db, ctx.now())
        db.commit()
    return sent


def run_price_moves(ctx: JobContext) -> int:
    """N1, toutes les 15 min en séance."""
    if not is_market_open(ctx.now()) or not notifications_ready():
        return 0
    with ctx.session_factory() as db:
        sent = notify_price_moves(db, ctx.now())
        db.commit()
    return sent


def run_daily_recaps(ctx: JobContext) -> int:
    if not notifications_ready():
        return 0
    with ctx.session_factory() as db:
        sent = send_daily_recaps(db, ctx.now())
        db.commit()
    return sent


def run_order_reminders(ctx: JobContext) -> int:
    if not notifications_ready():
        return 0
    with ctx.session_factory() as db:
        sent = send_order_reminders(db, ctx.now())
        db.commit()
    return sent


def run_score_notifications(ctx: JobContext) -> int:
    """Après le passage du soir : photo des scores (N4, N6), puis N6."""
    day = ctx.now().astimezone(PARIS).date()
    with ctx.session_factory() as db:
        take_score_snapshot(db, day)
        db.commit()
        if not notifications_ready():
            return 0
        sent = notify_score_changes(db, day)
        db.commit()
    return sent


def run_weekly_recaps(ctx: JobContext) -> int:
    if not notifications_ready():
        return 0
    with ctx.session_factory() as db:
        sent = send_weekly_recaps(db, ctx.now())
        db.commit()
    return sent
