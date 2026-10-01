"""Préférences de notification (spec 4.1, 5.1). Pas de commit ici."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NotificationPrefs, User

KINDS = ("price_move", "price_alert", "daily_recap", "weekly_recap", "order_reminder", "score_change")  # N1 à N6
DEFAULTS = {"price_move": True, "price_alert": True, "daily_recap": False, "weekly_recap": False,
            "order_reminder": True, "score_change": False}
DEFAULT_THRESHOLD = 5.0


def _defaults(user_id: uuid.UUID) -> NotificationPrefs:
    return NotificationPrefs(user_id=user_id, **DEFAULTS, move_threshold_pct=DEFAULT_THRESHOLD)


def get_prefs(db: Session, user_id: uuid.UUID) -> NotificationPrefs:
    """La ligne du membre, ou un objet non enregistré avec les valeurs par défaut."""
    return db.get(NotificationPrefs, user_id) or _defaults(user_id)


def save_prefs(db: Session, user_id: uuid.UUID, values: dict) -> NotificationPrefs:
    row = db.get(NotificationPrefs, user_id)
    if row is None:
        row = _defaults(user_id)
        db.add(row)
    for key, value in values.items():
        setattr(row, key, value)
    db.flush()
    return row


def recipients(db: Session, kind: str) -> list[tuple[User, NotificationPrefs]]:
    """Comptes validés qui ont activé `kind`, avec leurs préférences."""
    rows = db.execute(
        select(User, NotificationPrefs).outerjoin(NotificationPrefs, NotificationPrefs.user_id == User.id)
        .where(User.email_verified_at.is_not(None)).order_by(User.email)
    ).all()
    chosen = [(user, prefs or _defaults(user.id)) for user, prefs in rows]
    return [(user, prefs) for user, prefs in chosen if getattr(prefs, kind)]
