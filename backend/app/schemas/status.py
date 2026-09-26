from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job: str
    last_success_at: datetime | None
    last_error_at: datetime | None
    last_error: str | None
    last_count: int


class IndexQuote(BaseModel):
    id: int
    yahoo_ticker: str
    name: str
    price: float | None
    change_pct: float | None
    as_of: datetime | None


class StatusResponse(BaseModel):
    market_open: bool
    jobs: list[JobStatus]
    indices: list[IndexQuote]
