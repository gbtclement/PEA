"""Tâches du worker qui envoient les notifications N1 à N6 (spec 5.1)."""
from app.jobs.context import JobContext
from app.services.market_calendar import is_market_open
from app.services.notifications.moves import notify_price_moves
from app.services.notifications.price_alerts import check_price_alerts
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
