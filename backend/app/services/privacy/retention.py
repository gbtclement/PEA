"""Durées de conservation (spec 6.5), appliquées chaque nuit par la tâche « cleanup »."""
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import AuthSession, DataExport, EmailCode, EmailLog, MoveNotice, ScoreSnapshot, User
from app.services.mail.outbox import enqueue
from app.services.market_calendar import PARIS
from app.services.privacy.erasure import erase_account

UNVERIFIED_TTL = timedelta(days=7)
EMAIL_LOG_TTL = timedelta(days=90)
INACTIVITY = timedelta(days=3 * 365)
INACTIVITY_GRACE = timedelta(days=30)
SNAPSHOT_TTL = timedelta(days=14)
MOVE_NOTICE_TTL = timedelta(days=7)


def _activity():
    """Dernier signe de vie : création, connexion, ou usage d'une session « rester connecté »."""
    return func.greatest(User.created_at, func.coalesce(User.last_login_at, User.created_at),
                         func.coalesce(User.last_seen_at, User.created_at))


def run_retention(db: Session, now: datetime) -> dict[str, int]:
    """Supprime ce qui a dépassé sa durée de conservation. Pas de commit ici."""
    counts = {
        "unverified": db.execute(delete(User).where(User.email_verified_at.is_(None), User.role != "admin",
                                                    User.created_at < now - UNVERIFIED_TTL)).rowcount,
        "sessions": db.execute(delete(AuthSession).where(AuthSession.expires_at < now)).rowcount,
        "codes": db.execute(delete(EmailCode).where(EmailCode.expires_at < now)).rowcount,
        "exports": db.execute(delete(DataExport).where(DataExport.expires_at < now)).rowcount,
        "email_log": db.execute(delete(EmailLog).where(EmailLog.created_at < now - EMAIL_LOG_TTL,
                                                       EmailLog.status != "pending")).rowcount,
        "score_snapshots": db.execute(delete(ScoreSnapshot).where(
            ScoreSnapshot.day < now.astimezone(PARIS).date() - SNAPSHOT_TTL)).rowcount,
        "move_notices": db.execute(delete(MoveNotice).where(
            MoveNotice.day < now.astimezone(PARIS).date() - MOVE_NOTICE_TTL)).rowcount,
    }
    return counts | _inactivity(db, now)


def _inactivity(db: Session, now: datetime) -> dict[str, int]:
    """3 ans sans connexion : mail C8, puis suppression 30 jours après si toujours rien. Jamais un admin."""
    active = _activity()
    members = select(User).where(User.role != "admin", User.email_verified_at.is_not(None))
    # Revenu après l'avertissement : l'avertissement est oublié.
    for user in db.scalars(members.where(User.inactivity_warned_at.is_not(None), active > User.inactivity_warned_at)).all():
        user.inactivity_warned_at = None
    db.flush()
    warned = 0
    for user in db.scalars(members.where(User.inactivity_warned_at.is_(None), active < now - INACTIVITY)).all():
        user.inactivity_warned_at = now
        enqueue(db, "inactivity_warning", to=user.email, user_id=user.id,
                context={"first_name": user.first_name, "delete_on": now + INACTIVITY_GRACE})
        warned += 1
    db.flush()
    deleted = 0
    for user in db.scalars(members.where(User.inactivity_warned_at < now - INACTIVITY_GRACE,
                                         active <= User.inactivity_warned_at)).all():
        erase_account(db, user, now=now, reason="inactivity")
        deleted += 1
    return {"warned": warned, "inactive_deleted": deleted}
