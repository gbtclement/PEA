from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models import Security, SecurityQuote
from app.services.envelopes.rules import RULE_ENVELOPES, TO_CHECK
from app.services.fx import security_currency


class EnvelopeStatusOut(BaseModel):
    code: str
    status: str
    source: str
    override: str | None


class SecurityItem(BaseModel):
    id: int
    yahoo_ticker: str
    symbol: str
    name: str
    kind: str
    market: str
    country: str | None
    sector: str | None
    envelopes: list[EnvelopeStatusOut]
    price: float | None
    change_pct: float | None
    as_of: datetime | None
    currency: str  # devise du cours (EUR, USD, CHF…)

    @classmethod
    def build(cls, security: Security, quote: SecurityQuote | None) -> "SecurityItem":
        envelopes = []
        for code in RULE_ENVELOPES:
            row = security.envelope(code)
            envelopes.append(EnvelopeStatusOut(code=code, status=row.status if row else TO_CHECK,
                                               source=row.source if row else "auto", override=row.override if row else None))
        return cls(
            id=security.id, yahoo_ticker=security.yahoo_ticker, symbol=security.symbol, name=security.name,
            kind=security.kind, market=security.market, country=security.country, sector=security.sector,
            envelopes=envelopes,
            price=quote.price if quote else None,
            change_pct=quote.change_pct if quote else None,
            as_of=quote.as_of if quote else None,
            currency=security_currency(security),
        )


class SecurityList(BaseModel):
    items: list[SecurityItem]
    total: int


class EnvelopeUpdate(BaseModel):
    override: Literal["eligible", "a_verifier", "non_eligible"] | None
