from datetime import datetime

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.core.security import new_token, token_hash
from app.models import KnownDevice, User


def remember_device(db: Session, user: User, device_token: str | None, now: datetime) -> tuple[str, bool]:
    """Enregistre ce navigateur pour le compte. Renvoie (jeton du cookie cotalyx_device, faut-il alerter ?).

    Pas d'alerte pour le tout premier appareil d'un compte (l'inscription elle-même).
    """
    token = device_token or new_token()
    digest = token_hash(token)
    if db.get(KnownDevice, (user.id, digest)) is not None:
        return token, False
    had_devices = db.scalar(select(exists().where(KnownDevice.user_id == user.id)))
    db.add(KnownDevice(user_id=user.id, token_hash=digest, first_seen_at=now))
    db.flush()
    return token, bool(had_devices)
