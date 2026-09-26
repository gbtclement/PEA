from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.repositories.securities import search_securities
from app.schemas.securities import SecurityItem, SecurityList

router = APIRouter(tags=["securities"])


@router.get("/securities", response_model=SecurityList)
def list_securities(
    q: str | None = Query(None, max_length=100),
    kind: Literal["stock", "etf", "index"] | None = None,
    eligibility: Literal["eligible", "a_verifier", "non_eligible"] | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> SecurityList:
    rows, total = search_securities(db, q=q, kind=kind, eligibility=eligibility, limit=limit, offset=offset)
    return SecurityList(items=[SecurityItem.build(s, quote) for s, quote in rows], total=total)
