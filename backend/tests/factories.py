from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Security, SecurityScore


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


def make_score(db: Session, security: Security, **fields) -> SecurityScore:
    values = dict(
        computed_at=datetime(2026, 9, 28, 8, 0, tzinfo=UTC), total=60.0, technical=60.0, fundamental=60.0,
        components=[], available_ratio=1.0, liquid=True, history_days=250, avg_turnover_eur=1_000_000.0,
        eligible_for_top=True, perf_1w=1.0, perf_1m=2.0, perf_3m=3.0, perf_1y=4.0, sparkline=[1.0, 2.0],
    )
    values.update(fields)
    score = SecurityScore(security_id=security.id, **values)
    db.add(score)
    db.flush()
    return score
