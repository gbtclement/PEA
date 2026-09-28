from datetime import datetime, timedelta

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, normalize_email
from app.models import EmailCode, User
from app.models.user import LEGACY_EMAIL
from app.services.auth.accounts import TERMS_VERSION, find_user
from app.services.auth.codes import issue_link_token
from app.services.mail.outbox import enqueue

BOOTSTRAP_RESET_TTL = timedelta(hours=24)


def bootstrap_admin(db: Session, admin_email: str, now: datetime) -> str:
    """Au démarrage de l'API : ADMIN_EMAIL devient admin ; s'il n'existe pas, il reprend le compte « Moi ».

    Sans mot de passe (compte repris), un lien valable 24 h est envoyé, une seule fois.
    """
    if not admin_email.strip():
        return "ADMIN_EMAIL vide : aucun compte administrateur configuré."
    email = normalize_email(admin_email)
    user = find_user(db, email)
    if user is not None and user.email_verified_at is None:
        # Inscription jamais validée avec l'adresse de l'admin : rien ne prouve qu'elle vient de lui.
        db.delete(user)
        db.flush()
        user = None
    if user is None:
        user = db.scalar(select(User).where(User.email == LEGACY_EMAIL))
        if user is None:
            return f"Aucun compte {email} : il deviendra admin dès qu'il aura validé son inscription."
        user.email = email
    user.role, user.is_premium = "admin", True
    user.email_verified_at = user.email_verified_at or now
    pending = db.scalar(select(exists().where(EmailCode.user_id == user.id, EmailCode.purpose == "reset_password",
                                              EmailCode.used_at.is_(None), EmailCode.expires_at > now)))
    if user.password_hash is None and user.google_sub is None and not pending:
        token = issue_link_token(db, user, "reset_password", now, BOOTSTRAP_RESET_TTL)
        enqueue(db, "reset_password", to=user.email, user_id=user.id,
                context={"first_name": user.first_name, "token": token, "valid_minutes": 24 * 60})
        return f"{email} est admin : un lien pour choisir son mot de passe vient d'être envoyé."
    return f"{email} est admin."


def ensure_user(db: Session, *, email: str, password: str, first_name: str, last_name: str, admin: bool,
                now: datetime) -> User:
    """Crée ou met à jour un compte déjà validé (tests de bout en bout, dépannage). Jamais exposé par l'API."""
    user = find_user(db, email)
    if user is None:
        user = User(email=normalize_email(email), first_name=first_name, last_name=last_name)
        db.add(user)
    user.first_name, user.last_name = first_name, last_name
    user.password_hash = hash_password(password)
    user.email_verified_at = user.email_verified_at or now
    user.terms_accepted_at, user.terms_version = now, TERMS_VERSION
    user.role = "admin" if admin else user.role or "user"
    db.flush()
    return user
