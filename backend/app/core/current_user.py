from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import same
from app.models import AuthSession, User
from app.services.auth.sessions import SESSION_COOKIE, resolve_session

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def get_now() -> datetime:
    """Heure courante ; remplacée dans les tests."""
    return datetime.now(UTC)


def get_auth_session(request: Request, db: Session = Depends(get_db), now: datetime = Depends(get_now)) -> AuthSession | None:
    row = resolve_session(db, request.cookies.get(SESSION_COOKIE), now=now, settings=get_settings())
    if row is not None and request.method in UNSAFE_METHODS and not same(request.headers.get("X-CSRF-Token", ""), row.csrf_token):
        raise HTTPException(403, detail={"code": "csrf", "message": "Jeton de sécurité manquant ou périmé : rechargez la page."})
    return row


def get_optional_user(auth: AuthSession | None = Depends(get_auth_session), db: Session = Depends(get_db)) -> User | None:
    """Pages publiques : l'utilisateur s'il est connecté, sinon None."""
    return db.get(User, auth.user_id) if auth is not None else None


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    """Pages privées. Une session n'existe que pour un compte validé : l'utilisateur renvoyé l'est toujours."""
    if user is None:
        raise HTTPException(401, detail={"code": "not_authenticated", "message": "Connectez-vous pour accéder à cette page."})
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, detail={"code": "forbidden", "message": "Réservé aux administrateurs."})
    return user


def require_premium(user: User = Depends(get_current_user)) -> User:
    if not user.has_premium:
        raise HTTPException(403, detail={"code": "premium_required", "message": "Réservé aux membres Premium."})
    return user
