from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, needs_rehash, normalize_email, verify_password
from app.models import User
from app.services.auth.codes import (
    NOT_ME_TTL, RESEND_AFTER, RESET_TTL, CodeCheck, check_code, consume_link_token, issue_code, issue_link_token,
    last_code_at,
)
from app.services.auth.sessions import revoke_user_sessions
from app.services.mail.outbox import enqueue

TERMS_VERSION = "2026-09-28"  # à changer quand les CGU changent (étape 4)


def find_user(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def send_verification_code(db: Session, user: User, now: datetime) -> None:
    code = issue_code(db, user, "verify_email", now)
    enqueue(db, "verify_code", to=user.email, user_id=user.id, context={"first_name": user.first_name, "code": code})


def register(db: Session, *, first_name: str, last_name: str, email: str, password: str, now: datetime) -> None:
    """Crée (ou remplace, s'il n'a jamais été validé) un compte et envoie le code.

    Si l'adresse appartient déjà à un compte validé, rien ne change : son propriétaire reçoit une alerte,
    et la réponse de l'API reste identique pour ne pas révéler que le compte existe.
    """
    user = find_user(db, email)
    if user is not None and user.email_verified_at is not None:
        enqueue(db, "security_alert", to=user.email, user_id=user.id,
                context={"first_name": user.first_name, "event": "signup_attempt"},
                dedupe_key=f"signup_attempt:{user.id}:{now:%Y-%m-%d}")  # au plus une alerte par jour
        return
    if user is None:
        user = User(email=normalize_email(email), first_name=first_name, last_name=last_name)
        db.add(user)
    user.first_name, user.last_name = first_name, last_name
    user.password_hash = hash_password(password)
    user.terms_accepted_at, user.terms_version = now, TERMS_VERSION
    db.flush()
    send_verification_code(db, user, now)


def verify_email(db: Session, email: str, code: str, now: datetime) -> tuple[User | None, CodeCheck]:
    user = find_user(db, email)
    if user is None or user.email_verified_at is not None:
        return None, CodeCheck.INVALID
    result = check_code(db, user, "verify_email", code, now)
    if result != CodeCheck.OK:
        return None, result
    user.email_verified_at = now
    if user.email == normalize_email(get_settings().admin_email or "-"):
        user.role, user.is_premium = "admin", True
    enqueue(db, "welcome", to=user.email, user_id=user.id, context={"first_name": user.first_name})
    return user, result


def resend_code(db: Session, email: str, now: datetime) -> None:
    user = find_user(db, email)
    if user is None or user.email_verified_at is not None:
        return
    last = last_code_at(db, user, "verify_email")
    if last is not None and now - last < RESEND_AFTER:
        return
    send_verification_code(db, user, now)


def authenticate(db: Session, email: str, password: str) -> User | None:
    """Le compte si le mot de passe est bon (validé ou non), sinon None. Même durée dans tous les cas."""
    user = find_user(db, email)
    if not verify_password(user.password_hash if user else None, password):
        return None
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return user


def alert_new_device(db: Session, user: User, device: str, now: datetime) -> None:
    token = issue_link_token(db, user, "not_me", now, NOT_ME_TTL)
    enqueue(db, "new_device", to=user.email, user_id=user.id,
            context={"first_name": user.first_name, "device": device, "when": now, "token": token})


def request_password_reset(db: Session, email: str, now: datetime) -> None:
    user = find_user(db, email)
    if user is None or user.email_verified_at is None:
        return
    token = issue_link_token(db, user, "reset_password", now, RESET_TTL)
    enqueue(db, "reset_password", to=user.email, user_id=user.id,
            context={"first_name": user.first_name, "token": token, "valid_minutes": int(RESET_TTL.total_seconds() // 60)})


def reset_password(db: Session, token: str, password: str, now: datetime) -> User | None:
    user = consume_link_token(db, token, "reset_password", now)
    if user is None:
        return None
    user.password_hash = hash_password(password)
    user.failed_logins, user.locked_until = 0, None
    revoke_user_sessions(db, user.id)
    enqueue(db, "security_alert", to=user.email, user_id=user.id,
            context={"first_name": user.first_name, "event": "password_reset"})
    return user


def not_me(db: Session, token: str, now: datetime) -> User | None:
    """« Ce n'était pas moi » : tout le monde est déconnecté et l'ancien mot de passe ne marche plus."""
    user = consume_link_token(db, token, "not_me", now)
    if user is None:
        return None
    user.password_hash = None
    revoke_user_sessions(db, user.id)
    request_password_reset(db, user.email, now)
    return user
