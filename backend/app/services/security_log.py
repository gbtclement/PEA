import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.security import truncate_ip
from app.models import SecurityEvent

EVENT_KINDS = frozenset({
    "signup", "email_verified", "login_ok", "login_failed", "locked", "logout", "password_reset",
    "google_linked", "google_signup", "not_me", "admin_user_updated", "admin_user_deleted", "admin_settings_updated",
    "password_changed", "email_changed", "session_revoked",
})
RETENTION = timedelta(days=365)


def log_event(db: Session, kind: str, *, now: datetime, user_id: uuid.UUID | None = None, ip: str | None = None,
              details: dict | None = None, actor_id: uuid.UUID | None = None) -> None:
    """Ajoute une ligne au journal, dans la transaction en cours (pas de commit)."""
    if kind not in EVENT_KINDS:
        raise ValueError(f"Événement de sécurité inconnu : {kind}")
    db.add(SecurityEvent(kind=kind, user_id=user_id, actor_id=actor_id, ip=truncate_ip(ip), details=details or {},
                         created_at=now))


def purge_events(db: Session, now: datetime) -> int:
    return db.execute(delete(SecurityEvent).where(SecurityEvent.created_at < now - RETENTION)).rowcount
