from dataclasses import dataclass

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.models import Security, SecurityQuote
from app.services.eligibility.rules import classify_eligibility, effective_eligibility


@dataclass(frozen=True)
class SecurityUpsert:
    yahoo_ticker: str
    symbol: str
    name: str
    kind: str
    market: str
    isin: str | None
    country: str | None
    fixed_eligibility: str | None = None  # imposé par une liste de départ (ETF, indices)


def _apply_eligibility(security: Security, fixed: str | None) -> None:
    if fixed is not None:
        auto, source = fixed, "seed"
    else:
        auto, source = classify_eligibility(security.country, security.industry), "auto"
    security.eligibility, security.eligibility_source = effective_eligibility(
        auto, security.eligibility_override, auto_source=source
    )


def upsert_securities(session: Session, items: list[SecurityUpsert]) -> int:
    unique = {item.yahoo_ticker: item for item in items}
    existing = list(session.scalars(select(Security)))
    by_ticker = {s.yahoo_ticker: s for s in existing}
    by_isin = {s.isin: s for s in existing if s.isin}
    for item in unique.values():
        security = by_ticker.get(item.yahoo_ticker) or (by_isin.get(item.isin) if item.isin else None)
        if security is None:
            security = Security(eligibility_override=None, industry=None)
            session.add(security)
        security.yahoo_ticker = item.yahoo_ticker
        security.symbol = item.symbol
        security.name = item.name
        security.kind = item.kind
        security.market = item.market
        security.isin = item.isin
        security.country = item.country
        security.active = True
        _apply_eligibility(security, item.fixed_eligibility)
    session.flush()
    return len(unique)


def deactivate_missing(session: Session, seen_tickers: set[str]) -> int:
    result = session.execute(
        update(Security)
        .where(Security.active.is_(True), Security.yahoo_ticker.notin_(seen_tickers))
        .values(active=False)
    )
    return result.rowcount


def update_classification(security: Security, sector: str | None, industry: str | None) -> None:
    """Met à jour secteur/industrie (fondamentaux) et recalcule l'éligibilité des actions."""
    security.sector = sector
    security.industry = industry
    if security.kind == "stock" and security.eligibility_source != "seed":
        _apply_eligibility(security, None)


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_securities(
    session: Session,
    *,
    q: str | None,
    kind: str | None,
    eligibility: str | None,
    limit: int,
    offset: int,
) -> tuple[list[tuple[Security, SecurityQuote | None]], int]:
    stmt = (
        select(Security, SecurityQuote)
        .outerjoin(SecurityQuote, SecurityQuote.security_id == Security.id)
        .where(Security.active.is_(True))
    )
    stmt = stmt.where(Security.kind == kind) if kind else stmt.where(Security.kind != "index")
    if eligibility:
        stmt = stmt.where(Security.eligibility == eligibility)
    if q and q.strip():
        pattern = f"%{escape_like(q.strip())}%"
        stmt = stmt.where(or_(
            Security.name.ilike(pattern, escape="\\"),
            Security.symbol.ilike(pattern, escape="\\"),
            Security.isin.ilike(pattern, escape="\\"),
        ))
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.execute(stmt.order_by(Security.name, Security.id).limit(limit).offset(offset)).all()
    return [(security, quote) for security, quote in rows], total
