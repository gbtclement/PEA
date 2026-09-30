from app.jobs.context import JobContext
from app.services.ratelimit import purge_hits
from app.services.security_log import purge_events


def purge_security_data(ctx: JobContext) -> int:
    """Chaque nuit : journal de plus de 12 mois et compteurs de plus d'un jour."""
    now = ctx.now()
    with ctx.session_factory() as db:
        removed = purge_events(db, now) + purge_hits(db, now)
        db.commit()
    return removed
