"""Gestion des comptes par un administrateur : liste, modification, suppression, garde-fous."""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.core.security import normalize_email
from app.models import User
from app.services.auth.sessions import revoke_user_sessions
from app.services.mail.outbox import enqueue
from app.services.privacy.erasure import erase_account
from app.services.security_log import log_event

PAGE_SIZE = 50
_ACCENTED = "àâäáãéèêëíìîïóòôöõúùûüçñ"
_PLAIN = "aaaaaeeeeiiiiooooouuuucn"
_FOLD = str.maketrans(_ACCENTED, _PLAIN)
SORTS = {
    "email": User.email, "first_name": User.first_name, "last_name": User.last_name, "role": User.role,
    "is_premium": User.is_premium, "verified": User.email_verified_at, "created_at": User.created_at,
    "last_login_at": User.last_login_at,
}


class AdminError(Exception):
    """Refus d'un garde-fou ; levée avant toute écriture en base."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _fold(column) -> ColumnElement:
    """Minuscules sans accents, côté SQL (sans l'extension unaccent)."""
    return func.translate(func.lower(column), _ACCENTED, _PLAIN)


@dataclass(frozen=True)
class UserPage:
    items: list[User]
    total: int


def list_users(db: Session, *, q: str, sort: str, order: str, page: int) -> UserPage:
    stmt = select(User)
    for word in q.lower().translate(_FOLD).split():  # chaque mot doit se trouver dans le mail, le prénom ou le nom
        pattern = f"%{word}%"
        stmt = stmt.where(or_(_fold(User.email).like(pattern), _fold(User.first_name).like(pattern),
                              _fold(User.last_name).like(pattern)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    column = SORTS[sort]
    ordering = column.asc().nulls_last() if order == "asc" else column.desc().nulls_last()
    rows = db.scalars(stmt.order_by(ordering, User.id).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)).all()
    return UserPage(list(rows), total)


def _admin_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User).where(User.role == "admin"))


def update_user(db: Session, *, actor: User, target: User, changes: dict, now: datetime) -> User:
    """Applique les champs fournis. Tous les contrôles passent avant la première écriture."""
    if changes.get("role") == "user" and target.role == "admin":
        if target.id == actor.id:
            raise AdminError(400, "self_demotion", "Vous ne pouvez pas retirer votre propre rôle d'administrateur.")
        if _admin_count(db) <= 1:
            raise AdminError(400, "last_admin", "Il doit rester au moins un administrateur.")
    new_email = normalize_email(changes["email"]) if changes.get("email") else None
    if new_email == target.email:
        new_email = None
    if new_email and db.scalar(select(User.id).where(User.email == new_email)) is not None:
        raise AdminError(409, "email_taken", "Cette adresse est déjà utilisée par un autre compte.")

    changed = [field for field in ("first_name", "last_name", "role", "is_premium")
               if changes.get(field) is not None and changes[field] != getattr(target, field)]
    for field in changed:
        setattr(target, field, changes[field])
    old_email = target.email
    if new_email:
        target.email = new_email
        target.email_verified_at = target.email_verified_at or now  # l'admin en prend la responsabilité
        changed.append("email")
    if not changed:
        return target
    if {"role", "email"} & set(changed):  # comme après un changement de mot de passe : tout est à rouvrir
        revoke_user_sessions(db, target.id)
    log_event(db, "admin_user_updated", now=now, user_id=target.id, actor_id=actor.id, details={"fields": changed})
    context = {"first_name": target.first_name}
    if new_email:
        for address in (old_email, new_email):
            enqueue(db, "security_alert", to=address, user_id=target.id,
                    context={**context, "event": "email_changed_by_admin"})
    elif set(changed) - {"is_premium"}:  # la bascule Premium n'est pas une question de sécurité
        enqueue(db, "security_alert", to=target.email, user_id=target.id, context={**context, "event": "admin_updated"})
    return target


def delete_user(db: Session, *, actor: User, target: User, confirm_email: str, now: datetime) -> None:
    if target.id == actor.id:
        raise AdminError(400, "self_delete", "Vous ne pouvez pas supprimer votre propre compte ici.")
    if normalize_email(confirm_email) != target.email:
        raise AdminError(400, "confirm_mismatch", "L'adresse retapée ne correspond pas au compte.")
    erase_account(db, target, now=now, actor=actor)
