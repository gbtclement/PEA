from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.repositories.data_status import list_statuses
from app.repositories.securities import search_securities
from app.schemas.status import IndexQuote, JobStatus, StatusResponse
from app.services.market_calendar import is_market_open

router = APIRouter(tags=["meta"])


@router.get("/status", response_model=StatusResponse)
def get_status(db: Session = Depends(get_db)) -> StatusResponse:
    rows, _ = search_securities(db, q=None, kind="index", envelope=None, limit=20, offset=0)
    return StatusResponse(
        market_open=is_market_open(datetime.now(UTC)),
        jobs=[JobStatus.model_validate(status) for status in list_statuses(db)],
        indices=[
            IndexQuote(
                id=s.id, yahoo_ticker=s.yahoo_ticker, name=s.name,
                price=q.price if q else None, change_pct=q.change_pct if q else None, as_of=q.as_of if q else None,
            )
            for s, q in rows
        ],
    )
