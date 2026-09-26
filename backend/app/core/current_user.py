from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import User

DEFAULT_USER_NAME = "Moi"


def ensure_default_user(session: Session) -> User:
    user = session.scalars(select(User).order_by(User.id).limit(1)).first()
    if user is None:
        user = User(name=DEFAULT_USER_NAME)
        session.add(user)
        session.commit()
    return user


def get_current_user(db: Session = Depends(get_db)) -> User:
    """Application mono-utilisateur pour l'instant.

    Point d'entrée unique : le jour où les comptes arrivent, seule cette fonction
    change (vérification d'une session ou d'un jeton), pas les routes.
    """
    return ensure_default_user(db)
