"""Limites anti-abus comptées en base sur une fenêtre glissante (spec 2.4). Les valeurs ne sont stockées qu'en empreinte."""
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.security import token_hash
from app.models import RateLimitHit

FIFTEEN_MINUTES = timedelta(minutes=15)
ONE_HOUR = timedelta(hours=1)
LIMITS: dict[str, tuple[int, timedelta]] = {
    "login_account": (10, FIFTEEN_MINUTES),  # échecs de connexion par adresse → blocage
    "login_ip": (30, FIFTEEN_MINUTES),       # échecs de connexion par IP → 429
    "signup_ip": (5, ONE_HOUR),              # inscriptions par IP
    "mail_account": (5, ONE_HOUR),           # codes et liens envoyés par adresse
    "mail_ip": (20, ONE_HOUR),               # demandes de code ou de lien par IP
    "oauth_state": (1, timedelta(minutes=10)),  # un « state » Google ne sert qu'une fois
    "password_check": (10, FIFTEEN_MINUTES),  # mots de passe actuels faux par compte (réglages, suppression)
    "checkout_user": (10, ONE_HOUR),  # passages en caisse Stripe par compte
}
CAPTCHA_AFTER = 3  # échecs de connexion (compte ou IP) avant de demander le captcha
KEEP = timedelta(days=1)


def _key(bucket: str, value: str) -> str:
    return token_hash(f"{bucket}:{value.strip().lower()}")


def record(db: Session, bucket: str, value: str, now: datetime) -> None:
    db.add(RateLimitHit(bucket=bucket, key_hash=_key(bucket, value), created_at=now))
    db.flush()


def count(db: Session, bucket: str, value: str, now: datetime) -> int:
    window = LIMITS[bucket][1]
    return db.scalar(select(func.count()).select_from(RateLimitHit).where(
        RateLimitHit.bucket == bucket, RateLimitHit.key_hash == _key(bucket, value),
        RateLimitHit.created_at > now - window)) or 0


def over(db: Session, bucket: str, value: str, now: datetime) -> bool:
    return count(db, bucket, value, now) >= LIMITS[bucket][0]


def clear(db: Session, bucket: str, value: str) -> None:
    db.execute(delete(RateLimitHit).where(RateLimitHit.bucket == bucket, RateLimitHit.key_hash == _key(bucket, value)))


def purge_hits(db: Session, now: datetime) -> int:
    return db.execute(delete(RateLimitHit).where(RateLimitHit.created_at < now - KEEP)).rowcount
