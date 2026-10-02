from pydantic import BaseModel
from sqlalchemy import Row


class ScreenerRow(BaseModel):
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
    perf_1w: float | None
    perf_1m: float | None
    perf_1y: float | None
    score: float | None
    pe: float | None
    dividend_yield: float | None
    liquid: bool
    available_ratio: float | None
    isin: str | None
    is_favorite: bool
    sparkline: list[float]

    @classmethod
    def fields_from(cls, row: Row) -> dict:
        security, quote, score, fundamentals, is_favorite = row
        return dict(
            id=security.id, yahoo_ticker=security.yahoo_ticker, symbol=security.symbol, name=security.name,
            kind=security.kind, market=security.market, country=security.country, sector=security.sector,
            eligibility=security.envelope_status("pea") or "a_verifier",
            price=quote.price if quote else None,
            change_pct=quote.change_pct if quote else None,
            perf_1w=score.perf_1w if score else None,
            perf_1m=score.perf_1m if score else None,
            perf_1y=score.perf_1y if score else None,
            score=score.total if score else None,
            pe=fundamentals.pe if fundamentals else None,
            dividend_yield=fundamentals.dividend_yield if fundamentals else None,
            liquid=bool(score and score.liquid),
            available_ratio=score.available_ratio if score else None,
            isin=security.isin,
            is_favorite=bool(is_favorite),
            sparkline=list(score.sparkline) if score and score.sparkline else [],
        )

    @classmethod
    def build(cls, row: Row) -> "ScreenerRow":
        return cls(**cls.fields_from(row))
