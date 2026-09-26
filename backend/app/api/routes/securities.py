from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.current_user import get_current_user
from app.core.db import get_db
from app.models import Security, SecurityQuote, User
from app.repositories.securities import search_securities, set_eligibility_override
from app.schemas.securities import EligibilityUpdate, SecurityItem, SecurityList

router = APIRouter(tags=["securities"])


@router.get("/securities", response_model=SecurityList)
def list_securities(
    q: str | None = Query(None, max_length=100),
    kind: Literal["stock", "etf", "index"] | None = None,
    eligibility: Literal["eligible", "a_verifier", "non_eligible"] | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    overridden: bool = False,
    db: Session = Depends(get_db),
) -> SecurityList:
    rows, total = search_securities(db, q=q, kind=kind, eligibility=eligibility, limit=limit, offset=offset, overridden=overridden)
    return SecurityList(items=[SecurityItem.build(s, quote) for s, quote in rows], total=total)


@router.patch("/securities/{security_id}/eligibility", response_model=SecurityItem)
def update_eligibility(
    security_id: int,
    update: EligibilityUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),  # point d'entrée unique de l'authentification future
) -> SecurityItem:
    security = db.get(Security, security_id)
    if security is None:
        raise HTTPException(status_code=404, detail="Titre introuvable")
    set_eligibility_override(security, update.override)
    db.commit()
    return SecurityItem.build(security, db.get(SecurityQuote, security_id))
