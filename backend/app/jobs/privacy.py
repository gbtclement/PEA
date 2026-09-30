import json

from sqlalchemy import select

from app.jobs.context import JobContext
from app.models import DataExport, User
from app.services.mail.outbox import enqueue
from app.services.privacy.export import EXPORT_TTL, build_export


def build_pending_exports(ctx: JobContext) -> int:
    """Toutes les 15 s : prépare les exports demandés, puis prévient par mail (C7)."""
    now, done = ctx.now(), 0
    with ctx.session_factory() as db:
        rows = db.scalars(select(DataExport).where(DataExport.status == "pending").with_for_update(skip_locked=True)).all()
        for row in rows:
            user = db.get(User, row.user_id)
            row.content = json.dumps(build_export(db, user, now), ensure_ascii=False, indent=2)
            row.status, row.ready_at, row.expires_at = "ready", now, now + EXPORT_TTL
            enqueue(db, "data_export_ready", to=user.email, user_id=user.id,
                    context={"first_name": user.first_name, "expires_at": row.expires_at})
            done += 1
        db.commit()
    return done
