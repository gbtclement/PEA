"""Durées de conservation (spec 6.5), appliquées chaque nuit par la tâche « cleanup »."""
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.models import AuthSession, DataExport, EmailCode, EmailLog, MoveNotice, ScoreSnapshot, StripeEvent, Subscription, User
from app.services.billing.access import ACCESS_STATUSES
from app.services.mail.outbox import enqueue
from app.services.market_calendar import PARIS
from app.services.privacy.erasure import email_fingerprint, erase_account

UNVERIFIED_TTL = timedelta(days=7)
EMAIL_LOG_TTL = timedelta(days=90)
INACTIVITY = timedelta(days=3 * 365)
INACTIVITY_GRACE = timedelta(days=30)
SNAPSHOT_TTL = timedelta(days=14)
MOVE_NOTICE_TTL = timedelta(days=7)
STRIPE_EVENTS_TTL = timedelta(days=30)
PENDING_EXPORT_TIMEOUT = timedelta(hours=1)
STUCK_ACCOUNT_DELETED = timedelta(days=7)


def _activity():
    """Dernier signe de vie : création, connexion, ou usage d'une session « rester connecté »."""
    return func.greatest(User.created_at, func.coalesce(User.last_login_at, User.created_at),
                         func.coalesce(User.last_seen_at, User.created_at))


def run_retention(db: Session, now: datetime) -> dict[str, int]:
    """Supprime ce qui a dépassé sa durée de conservation. Pas de commit ici."""
    db.execute(update(DataExport).where(DataExport.status == "pending",
                                        DataExport.created_at < now - PENDING_EXPORT_TIMEOUT).values(status="failed"))
    for row in db.scalars(select(EmailLog).where(EmailLog.kind == "account_deleted", EmailLog.status == "pending",
                                                 EmailLog.created_at < now - STUCK_ACCOUNT_DELETED)):
        row.recipient, row.status = email_fingerprint(row.recipient), "failed"  # sans SMTP, l'adresse ne reste pas
    counts = {
        "unverified": db.execute(delete(User).where(User.email_verified_at.is_(None), User.role != "admin",
                                                    User.created_at < now - UNVERIFIED_TTL)).rowcount,
        "sessions": db.execute(delete(AuthSession).where(AuthSession.expires_at < now)).rowcount,
        "codes": db.execute(delete(EmailCode).where(EmailCode.expires_at < now)).rowcount,
        "exports": db.execute(delete(DataExport).where(DataExport.expires_at < now)).rowcount,
        "email_log": db.execute(delete(EmailLog).where(EmailLog.created_at < now - EMAIL_LOG_TTL)).rowcount,
        "stripe_events": db.execute(delete(StripeEvent).where(StripeEvent.received_at < now - STRIPE_EVENTS_TTL)).rowcount,
        "score_snapshots": db.execute(delete(ScoreSnapshot).where(
            ScoreSnapshot.day < now.astimezone(PARIS).date() - SNAPSHOT_TTL)).rowcount,
        "move_notices": db.execute(delete(MoveNotice).where(
            MoveNotice.day < now.astimezone(PARIS).date() - MOVE_NOTICE_TTL)).rowcount,
    }
    return counts | _inactivity(db, now)


def _inactivity(db: Session, now: datetime) -> dict[str, int]:
    """3 ans sans connexion : mail C8, puis suppression 30 jours après si toujours rien. Jamais un admin ni un abonné."""
    active = _activity()
    paying = select(Subscription.user_id).where(Subscription.status.in_(tuple(ACCESS_STATUSES)))
    members = select(User).where(User.role != "admin", User.email_verified_at.is_not(None), User.id.not_in(paying))
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
