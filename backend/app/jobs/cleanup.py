from app.jobs.context import JobContext
from app.services.privacy.retention import run_retention
from app.services.ratelimit import purge_hits
from app.services.security_log import purge_events


def purge_security_data(ctx: JobContext) -> int:
    """Chaque nuit : durées de conservation (spec 6.5), journal de plus de 12 mois, compteurs de plus d'un jour."""
    now = ctx.now()
    with ctx.session_factory() as db:
        removed = sum(run_retention(db, now).values()) + purge_events(db, now) + purge_hits(db, now)
        db.commit()
    return removed
