import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import device_label, new_token, token_hash, truncate_ip
from app.models import AuthSession, User

SESSION_COOKIE = "pea_session"
CSRF_COOKIE = "pea_csrf"
DEVICE_COOKIE = "pea_device"
TOUCH_EVERY = timedelta(minutes=1)


@dataclass(frozen=True)
class NewSession:
    token: str
    csrf_token: str
    session: AuthSession


def lifetime(persistent: bool, settings: Settings) -> timedelta:
    return timedelta(days=settings.session_days) if persistent else timedelta(hours=settings.session_short_hours)


def open_session(db: Session, user: User, *, persistent: bool, ip: str | None, user_agent: str | None,
                 now: datetime, settings: Settings) -> NewSession:
    """Nouvelle session pour un compte validé. Seule l'empreinte du jeton est enregistrée."""
    token, csrf = new_token(), new_token()
    row = AuthSession(
        user_id=user.id, token_hash=token_hash(token), csrf_token=csrf, device=device_label(user_agent),
        ip=truncate_ip(ip), persistent=persistent, last_seen_at=now, expires_at=now + lifetime(persistent, settings),
    )
    db.add(row)
    user.last_login_at = now
    db.flush()
    return NewSession(token, csrf, row)


def resolve_session(db: Session, token: str | None, *, now: datetime, settings: Settings) -> AuthSession | None:
    if not token:
        return None
    row = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(token)))
    if row is None or row.expires_at <= now:
        return None
    if now - row.last_seen_at >= TOUCH_EVERY:  # au plus une écriture par minute
        row.last_seen_at = now
        row.expires_at = now + lifetime(row.persistent, settings)
        db.execute(update(User).where(User.id == row.user_id).values(last_seen_at=now))  # inactivité (spec 6.5)
        db.commit()
    return row


def revoke_session(db: Session, session_id: uuid.UUID) -> None:
    db.execute(delete(AuthSession).where(AuthSession.id == session_id))


def revoke_user_sessions(db: Session, user_id: uuid.UUID) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
