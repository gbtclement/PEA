from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.current_user import get_current_user
from app.core.db import get_db
from app.models import Favorite, Security, User

router = APIRouter(tags=["favorites"])


def _ensure_security(db: Session, security_id: int) -> None:
    if db.get(Security, security_id) is None:
        raise HTTPException(status_code=404, detail="Titre introuvable")


@router.put("/favorites/{security_id}", status_code=204)
def add_favorite(security_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    _ensure_security(db, security_id)
    if db.get(Favorite, (user.id, security_id)) is None:
        db.add(Favorite(user_id=user.id, security_id=security_id))
        db.commit()
    return Response(status_code=204)


@router.delete("/favorites/{security_id}", status_code=204)
def remove_favorite(security_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    favorite = db.get(Favorite, (user.id, security_id))
    if favorite is not None:
        db.delete(favorite)
        db.commit()
    return Response(status_code=204)
