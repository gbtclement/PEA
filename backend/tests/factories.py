from sqlalchemy.orm import Session

from app.models import Security


def make_security(
    db: Session,
    ticker: str,
    *,
    kind: str = "stock",
    eligibility: str = "eligible",
    country: str | None = "FR",
    active: bool = True,
    isin: str | None = None,
    name: str | None = None,
    market: str = "Euronext Paris",
) -> Security:
    security = Security(
        yahoo_ticker=ticker,
        symbol=ticker.split(".")[0],
        name=name or ticker,
        kind=kind,
        market=market,
        country=country,
        isin=isin,
        eligibility=eligibility,
        eligibility_source="auto",
        active=active,
    )
    db.add(security)
    db.flush()
    return security
