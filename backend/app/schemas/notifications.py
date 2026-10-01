import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NotificationPrefsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    price_move: bool
    price_alert: bool
    daily_recap: bool
    weekly_recap: bool
    order_reminder: bool
    score_change: bool
    move_threshold_pct: float


class NotificationPrefsIn(BaseModel):
    price_move: bool
    price_alert: bool
    daily_recap: bool
    weekly_recap: bool
    order_reminder: bool
    score_change: bool
    move_threshold_pct: float = Field(ge=1, le=50)


class PriceAlertIn(BaseModel):
    security_id: int
    direction: Literal["above", "below"]
    price: float = Field(gt=0, lt=1_000_000)


class PriceAlertUpdate(BaseModel):
    direction: Literal["above", "below"] | None = None
    price: float | None = Field(default=None, gt=0, lt=1_000_000)
    active: bool | None = None


class PriceAlertOut(BaseModel):
    id: uuid.UUID
    security_id: int
    symbol: str
    name: str
    currency: str
    direction: str
    price: float
    current_price: float | None
    active: bool
    triggered_at: datetime | None
    created_at: datetime


class UnsubscribeOut(BaseModel):
    kind: str | None
    label: str | None
