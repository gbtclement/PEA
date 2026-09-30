from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.security import new_code, new_token, same, token_hash
from app.models import EmailCode, User

CODE_TTL = timedelta(minutes=15)
RESET_TTL = timedelta(minutes=30)
NOT_ME_TTL = timedelta(days=7)
RESEND_AFTER = timedelta(seconds=60)
MAX_ATTEMPTS = 5


class CodeCheck(StrEnum):
    OK = "ok"
    INVALID = "invalid"
    EXPIRED = "expired"
    TOO_MANY = "too_many"


def _cancel_pending(db: Session, user: User, purpose: str, now: datetime) -> None:
    db.execute(update(EmailCode).where(EmailCode.user_id == user.id, EmailCode.purpose == purpose,
                                       EmailCode.used_at.is_(None)).values(used_at=now))


def issue_code(db: Session, user: User, purpose: str, now: datetime) -> str:
    """Nouveau code à 6 chiffres ; les codes précédents du même type ne marchent plus."""
    _cancel_pending(db, user, purpose, now)
    code = new_code()
    db.add(EmailCode(user_id=user.id, purpose=purpose, code_hash=token_hash(code), expires_at=now + CODE_TTL,
                     created_at=now))
    db.flush()
    return code


def last_code_at(db: Session, user: User, purpose: str) -> datetime | None:
    return db.scalar(select(EmailCode.created_at).where(EmailCode.user_id == user.id, EmailCode.purpose == purpose)
                     .order_by(EmailCode.id.desc()).limit(1))


def check_code(db: Session, user: User, purpose: str, code: str, now: datetime) -> CodeCheck:
    row = db.scalar(select(EmailCode).where(EmailCode.user_id == user.id, EmailCode.purpose == purpose,
                                            EmailCode.used_at.is_(None)).order_by(EmailCode.id.desc()).limit(1))
    if row is None:
        return CodeCheck.INVALID
    if row.expires_at <= now:
        return CodeCheck.EXPIRED
    if row.attempts >= MAX_ATTEMPTS:
        return CodeCheck.TOO_MANY
    if not same(row.code_hash, token_hash(code.strip())):
        row.attempts += 1
        return CodeCheck.TOO_MANY if row.attempts >= MAX_ATTEMPTS else CodeCheck.INVALID
    row.used_at = now
    return CodeCheck.OK


def issue_link_token(db: Session, user: User, purpose: str, now: datetime, ttl: timedelta) -> str:
    """Jeton long (256 bits) pour un lien envoyé par mail ; les liens précédents du même type ne marchent plus."""
    _cancel_pending(db, user, purpose, now)
    token = new_token()
    db.add(EmailCode(user_id=user.id, purpose=purpose, code_hash=token_hash(token), expires_at=now + ttl, created_at=now))
    db.flush()
    return token


def _live_link(db: Session, token: str, purpose: str, now: datetime) -> EmailCode | None:
    return db.scalar(select(EmailCode).where(EmailCode.code_hash == token_hash(token), EmailCode.purpose == purpose,
                                             EmailCode.used_at.is_(None), EmailCode.expires_at > now))


def link_token_valid(db: Session, token: str, purpose: str, now: datetime) -> bool:
    """Le lien marche-t-il encore ? Ne le consomme pas."""
    return _live_link(db, token, purpose, now) is not None


def consume_link_token(db: Session, token: str, purpose: str, now: datetime) -> User | None:
    row = _live_link(db, token, purpose, now)
    if row is None:
        return None
    row.used_at = now
    return db.get(User, row.user_id)
