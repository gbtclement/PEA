"""Tâches du worker qui envoient les notifications N1 à N6 (spec 5.1)."""
from app.jobs.context import JobContext
from app.services.notifications.price_alerts import check_price_alerts
from app.services.notifications.send import notifications_ready


def run_price_alerts(ctx: JobContext) -> int:
    if not notifications_ready():
        return 0
    with ctx.session_factory() as db:
        sent = check_price_alerts(db, ctx.now())
        db.commit()
    return sent
