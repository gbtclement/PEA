from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PlanOut(BaseModel):
    interval: str
    amount: int  # centimes TTC
    currency: str


class PlansOut(BaseModel):
    configured: bool
    plans: list[PlanOut]
    yearly_saving_pct: int | None


class SubscriptionOut(BaseModel):
    source: str  # admin | offered | subscription | none
    status: str | None
    interval: str | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    has_customer: bool  # « Gérer mon abonnement » possible (factures d'un ancien abonnement comprises)


class CheckoutIn(BaseModel):
    interval: Literal["month", "year"]
    accept_cgv: bool
    waive_withdrawal: bool


class SyncIn(BaseModel):
    session_id: str = Field(min_length=1, max_length=255)


class RedirectOut(BaseModel):
    url: str
