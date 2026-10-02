from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models import Security, SecurityQuote


class SecurityItem(BaseModel):
    id: int
    yahoo_ticker: str
    symbol: str
    name: str
    kind: str
    market: str
    country: str | None
    sector: str | None
    eligibility: str
    eligibility_source: str
    eligibility_override: str | None
    price: float | None
    change_pct: float | None
    as_of: datetime | None

    @classmethod
    def build(cls, security: Security, quote: SecurityQuote | None) -> "SecurityItem":
        pea = security.envelope("pea")
        return cls(
            id=security.id, yahoo_ticker=security.yahoo_ticker, symbol=security.symbol, name=security.name,
            kind=security.kind, market=security.market, country=security.country, sector=security.sector,
            eligibility=pea.status if pea else "a_verifier",
            eligibility_source=pea.source if pea else "auto",
            eligibility_override=pea.override if pea else None,
            price=quote.price if quote else None,
            change_pct=quote.change_pct if quote else None,
            as_of=quote.as_of if quote else None,
        )


class SecurityList(BaseModel):
    items: list[SecurityItem]
    total: int


class EligibilityUpdate(BaseModel):
    override: Literal["eligible", "a_verifier", "non_eligible"] | None
