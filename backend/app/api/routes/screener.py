from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.current_user import get_optional_user
from app.core.db import get_db
from app.models import User
from app.repositories.screener import screener_rows
from app.schemas.screener import ScreenerRow

router = APIRouter(tags=["screener"])


@router.get("/screener", response_model=list[ScreenerRow])
def get_screener(
    kind: Literal["stock", "etf"] | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> list[ScreenerRow]:
    return [ScreenerRow.build(row) for row in screener_rows(db, user.id if user else None, kind=kind)]
