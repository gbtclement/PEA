from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.current_user import require_admin
from app.core.db import get_db
from app.models import Security, SecurityFundamentals, SecurityQuote, User
from app.repositories.envelopes import set_envelope_override
from app.repositories.securities import search_securities
from app.schemas.securities import EnvelopeUpdate, SecurityItem, SecurityList

router = APIRouter(tags=["securities"])


@router.get("/securities", response_model=SecurityList)
def list_securities(
    q: str | None = Query(None, max_length=100),
    kind: Literal["stock", "etf", "index"] | None = None,
    envelope: Literal["pea", "pea_pme"] | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    overridden: bool = False,
    db: Session = Depends(get_db),
) -> SecurityList:
    rows, total = search_securities(db, q=q, kind=kind, envelope=envelope, limit=limit, offset=offset, overridden=overridden,
                                     priced_only=not overridden)
    return SecurityList(items=[SecurityItem.build(s, quote) for s, quote in rows], total=total)


@router.patch("/securities/{security_id}/envelopes/{code}", response_model=SecurityItem)
def update_envelope(
    security_id: int,
    code: Literal["pea", "pea_pme"],
    update: EnvelopeUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> SecurityItem:
    security = db.get(Security, security_id)
    if security is None:
        raise HTTPException(status_code=404, detail="Titre introuvable")
    set_envelope_override(security, code, update.override, db.get(SecurityFundamentals, security_id))
    db.commit()
    return SecurityItem.build(security, db.get(SecurityQuote, security_id))
