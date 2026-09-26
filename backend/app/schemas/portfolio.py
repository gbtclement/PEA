from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class OrderIn(BaseModel):
    security_id: int
    trade_date: date
    side: Literal["buy", "sell"]
    quantity: int = Field(gt=0, le=1_000_000)
    unit_price: float = Field(gt=0, le=1_000_000)
    fee: float | None = Field(default=None, ge=0, le=10_000)
    note: str | None = Field(default=None, max_length=200)


class OrderOut(BaseModel):
    id: int
    security_id: int
    symbol: str
    name: str
    trade_date: date
    side: str
    quantity: int
    unit_price: float
    fee: float
    amount: float
    note: str | None


class CounterOut(BaseModel):
    year: int
    count: int
    min_orders: int
    remaining: int
    expected_by_now: float
    behind: bool
    penalty_fee: float


class PositionOut(BaseModel):
    security_id: int
    symbol: str
    name: str
    sector: str | None
    kind: str
    quantity: int
    avg_cost: float
    price: float | None
    change_pct: float | None
    value: float
    gain: float
    gain_pct: float | None
    weight: float


class SectorOut(BaseModel):
    sector: str
    value: float
    weight: float


class PortfolioOut(BaseModel):
    total_value: float
    invested: float
    gain: float
    gain_pct: float | None
    day_change: float
    day_change_pct: float | None
    realized_gain: float
    positions: list[PositionOut]
    sectors: list[SectorOut]
    counter: CounterOut


class HistoryPointOut(BaseModel):
    date: date
    value: float
    invested: float
