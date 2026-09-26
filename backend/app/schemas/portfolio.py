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
