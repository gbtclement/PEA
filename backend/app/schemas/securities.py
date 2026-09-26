from datetime import datetime

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
    price: float | None
    change_pct: float | None
    as_of: datetime | None

    @classmethod
    def build(cls, security: Security, quote: SecurityQuote | None) -> "SecurityItem":
        return cls(
            id=security.id, yahoo_ticker=security.yahoo_ticker, symbol=security.symbol, name=security.name,
            kind=security.kind, market=security.market, country=security.country, sector=security.sector,
            eligibility=security.eligibility,
            price=quote.price if quote else None,
            change_pct=quote.change_pct if quote else None,
            as_of=quote.as_of if quote else None,
        )


class SecurityList(BaseModel):
    items: list[SecurityItem]
    total: int
