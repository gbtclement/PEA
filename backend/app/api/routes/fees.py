from fastapi import APIRouter, Query

from app.schemas.security_detail import FeeEstimate
from app.services.fees import broker_fee

router = APIRouter(tags=["fees"])


@router.get("/fees/estimate", response_model=FeeEstimate)
def estimate_fee(amount: float = Query(..., ge=0, le=1_000_000)) -> FeeEstimate:
    fee, rate = broker_fee(amount)
    return FeeEstimate(amount=amount, fee=fee, rate=rate)
