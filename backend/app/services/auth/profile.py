"""Réglages du profil : nom, mot de passe, adresse mail."""
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, normalize_email, verify_password
from app.models import AuthSession, User
from app.services.auth.codes import CodeCheck, check_code, issue_code, pending_new_email
from app.services.mail.outbox import enqueue
from app.services.security_log import log_event


def password_ok(user: User, password: str | None) -> bool:
    """Un compte sans mot de passe (Google seul) n'a rien à confirmer."""
    return not user.has_password or (password is not None and verify_password(user.password_hash, password))


def change_password(db: Session, user: User, new_password: str, *, keep_session: AuthSession, now: datetime,
                    ip: str | None) -> None:
    user.password_hash = hash_password(new_password)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.id != keep_session.id))
    log_event(db, "password_changed", now=now, user_id=user.id, ip=ip)
    enqueue(db, "security_alert", to=user.email, user_id=user.id,
            context={"first_name": user.first_name, "event": "password_changed"})


def request_email_change(db: Session, user: User, new_email: str, now: datetime) -> None:
    """Envoie un code à la nouvelle adresse, sauf si elle est déjà prise (sans le dire)."""
    new_email = normalize_email(new_email)
    if new_email == user.email or db.scalar(select(User.id).where(User.email == new_email)) is not None:
        return
    code = issue_code(db, user, "change_email", now, new_email=new_email)
    enqueue(db, "verify_code", to=new_email, user_id=user.id, context={"first_name": user.first_name, "code": code})


class EmailTaken(Exception):
    """La nouvelle adresse a été prise entre la demande et la validation."""


def confirm_email_change(db: Session, user: User, code: str, now: datetime, ip: str | None) -> CodeCheck:
    new_email = pending_new_email(db, user)
    result = check_code(db, user, "change_email", code, now)
    if result != CodeCheck.OK:
        return result
    if new_email is None or db.scalar(select(User.id).where(User.email == new_email)) is not None:
        raise EmailTaken
    old_email = user.email
    user.email = new_email
    log_event(db, "email_changed", now=now, user_id=user.id, ip=ip)
    enqueue(db, "security_alert", to=old_email, user_id=user.id,
            context={"first_name": user.first_name, "event": "email_changed"})
    return result
