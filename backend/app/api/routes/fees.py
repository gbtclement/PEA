from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.current_user import get_current_user
from app.core.db import get_db
from app.models import User
from app.repositories.user_settings import user_fee_grid
from app.schemas.security_detail import FeeEstimate
from app.services.fees import broker_fee

router = APIRouter(tags=["fees"])


@router.get("/fees/estimate", response_model=FeeEstimate)
def estimate_fee(
    amount: float = Query(..., ge=0, le=1_000_000), db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> FeeEstimate:
    fee, rate = broker_fee(amount, user_fee_grid(db, user.id))
    return FeeEstimate(amount=amount, fee=fee, rate=rate)
