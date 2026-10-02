from dataclasses import dataclass

from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.orm import Session

from app.models import Security, SecurityEnvelope, SecurityFundamentals, SecurityQuote
from app.repositories.envelopes import refresh_envelopes
from app.services.envelopes.rules import ELIGIBLE


@dataclass(frozen=True)
class SecurityUpsert:
    yahoo_ticker: str
    symbol: str
    name: str
    kind: str
    market: str
    isin: str | None
    country: str | None
    currency: str | None = None
    source: str | None = None


def upsert_securities(session: Session, items: list[SecurityUpsert]) -> int:
    unique = {item.yahoo_ticker: item for item in items}
    existing = list(session.scalars(select(Security)))
    fundamentals = {f.security_id: f for f in session.scalars(select(SecurityFundamentals))}
    by_ticker = {s.yahoo_ticker: s for s in existing}
    by_isin = {s.isin: s for s in existing if s.isin}
    for item in unique.values():
        security = by_ticker.get(item.yahoo_ticker) or (by_isin.get(item.isin) if item.isin else None)
        if security is None:
            security = Security(industry=None)
            session.add(security)
        security.yahoo_ticker = item.yahoo_ticker
        security.symbol = item.symbol
        security.name = item.name
        security.kind = item.kind
        security.market = item.market
        security.isin = item.isin
        security.country = item.country
        security.currency = item.currency
        security.source = item.source
        security.active = True
        refresh_envelopes(security, fundamentals.get(security.id))
    session.flush()
    return len(unique)


def deactivate_missing(session: Session, seen_tickers: set[str], sources: set[str] | None = None) -> int:
    """Désactive les titres absents des listes ; avec `sources`, seulement ceux des sources qui ont répondu."""
    stmt = update(Security).where(Security.active.is_(True), Security.yahoo_ticker.notin_(seen_tickers))
    if sources is not None:
        stmt = stmt.where(Security.source.in_(sources))
    result = session.execute(stmt.values(active=False))
    return result.rowcount


def update_classification(security: Security, sector: str | None, industry: str | None,
                          fundamentals: SecurityFundamentals | None) -> None:
    """Met à jour secteur/industrie (fondamentaux) et recalcule les enveloppes.

    Une réponse Yahoo incomplète (sans secteur/industrie) ne doit pas effacer une classification connue.
    """
    security.sector = sector or security.sector
    security.industry = industry or security.industry
    refresh_envelopes(security, fundamentals)


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_securities(
    session: Session,
    *,
    q: str | None,
    kind: str | None,
    envelope: str | None,
    limit: int,
    overridden: bool = False,
    offset: int,
) -> tuple[list[tuple[Security, SecurityQuote | None]], int]:
    stmt = (
        select(Security, SecurityQuote)
        .outerjoin(SecurityQuote, SecurityQuote.security_id == Security.id)
        .where(Security.active.is_(True))
    )
    stmt = stmt.where(Security.kind == kind) if kind else stmt.where(Security.kind != "index")
    if envelope:
        stmt = stmt.where(exists().where(SecurityEnvelope.security_id == Security.id, SecurityEnvelope.envelope == envelope,
                                         SecurityEnvelope.status == ELIGIBLE))
    if overridden:
        stmt = stmt.where(exists().where(SecurityEnvelope.security_id == Security.id, SecurityEnvelope.override.is_not(None)))
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
