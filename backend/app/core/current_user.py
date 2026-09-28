from datetime import UTC, datetime

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import User
from app.models.user import LEGACY_EMAIL


def ensure_default_user(session: Session) -> User:
    user = session.scalars(select(User).where(User.email == LEGACY_EMAIL)).first()
    if user is None:
        user = User(email=LEGACY_EMAIL, first_name="Moi", last_name="", role="admin", is_premium=True,
                    email_verified_at=datetime.now(UTC))
        session.add(user)
        session.commit()
    return user


def get_current_user(db: Session = Depends(get_db)) -> User:
    """Application mono-utilisateur pour l'instant.

    Point d'entrée unique : le jour où les comptes arrivent, seule cette fonction
    change (vérification d'une session ou d'un jeton), pas les routes.
    """
    return ensure_default_user(db)
