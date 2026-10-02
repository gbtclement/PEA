import math
from collections.abc import Collection
from datetime import date

from sqlalchemy import Row, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import DailyPrice, Security, SecurityFundamentals, SecurityQuote
from app.providers.base import DailyBar, Fundamentals, Quote

UPSERT_CHUNK_ROWS = 5000


def refreshable_securities(session: Session) -> list[Security]:
    """Titres actifs dont on suit les cours : tous, quelle que soit leur enveloppe."""
    return list(session.scalars(select(Security).where(Security.active.is_(True))))


def ticker_ids(session: Session, tickers: list[str]) -> dict[str, int]:
    if not tickers:
        return {}
    rows = session.execute(select(Security.yahoo_ticker, Security.id).where(Security.yahoo_ticker.in_(tickers)))
    return {ticker: security_id for ticker, security_id in rows}


def upsert_quotes(session: Session, quotes: dict[int, Quote], *, only_if_newer: bool = False) -> int:
    if not quotes:
        return 0
    rows = [
        {"security_id": sid, "price": q.price, "previous_close": q.previous_close,
         "change_pct": q.change_pct, "volume": q.volume, "as_of": q.as_of}
        for sid, q in quotes.items()
    ]
    stmt = pg_insert(SecurityQuote).values(rows)
    updated = {col: stmt.excluded[col] for col in ("price", "previous_close", "change_pct", "volume", "as_of")}
    session.execute(stmt.on_conflict_do_update(
        index_elements=["security_id"],
        set_={**updated, "updated_at": func.now()},
        where=(SecurityQuote.as_of < stmt.excluded.as_of) if only_if_newer else None,
    ))
    return len(rows)


def last_two_closes(session: Session, security_ids: list[int]) -> dict[int, list[DailyPrice]]:
    """Les deux dernières séances de chaque titre, la plus récente en premier."""
    if not security_ids:
        return {}
    ranked = select(
        DailyPrice,
        func.row_number().over(partition_by=DailyPrice.security_id, order_by=DailyPrice.date.desc()).label("rn"),
    ).where(DailyPrice.security_id.in_(security_ids)).subquery()
    rows = session.execute(select(ranked).where(ranked.c.rn <= 2).order_by(ranked.c.security_id, ranked.c.rn)).all()
    result: dict[int, list[DailyPrice]] = {}
    for row in rows:
        result.setdefault(row.security_id, []).append(row)
    return result


def stored_close(session: Session, security_id: int, day: date) -> float | None:
    return session.scalar(select(DailyPrice.close).where(DailyPrice.security_id == security_id, DailyPrice.date == day))


def delete_daily_prices(session: Session, security_id: int) -> None:
    session.execute(delete(DailyPrice).where(DailyPrice.security_id == security_id))


def upsert_daily_bars(session: Session, security_id: int, bars: list[DailyBar]) -> int:
    if not bars:
        return 0
    rows = [
        {"security_id": security_id, "date": b.date, "open": b.open, "high": b.high, "low": b.low,
         "close": b.close, "volume": b.volume}
        for b in bars
    ]
    # PostgreSQL limite une requête à 65 535 paramètres (7 par ligne) : un historique complet passe en plusieurs fois.
    for start in range(0, len(rows), UPSERT_CHUNK_ROWS):
        stmt = pg_insert(DailyPrice).values(rows[start:start + UPSERT_CHUNK_ROWS])
        updated = {col: stmt.excluded[col] for col in ("open", "high", "low", "close", "volume")}
        session.execute(stmt.on_conflict_do_update(index_elements=["security_id", "date"], set_=updated))
    return len(rows)


def all_daily_prices(session: Session, security_id: int) -> list[DailyPrice]:
    return list(session.scalars(
        select(DailyPrice).where(DailyPrice.security_id == security_id).order_by(DailyPrice.date)
    ))


def daily_series(session: Session, since: date, security_ids: Collection[int] | None = None) -> dict[int, list[Row]]:
    """Colonnes utiles seulement (pas d'objets ORM) : des millions de lignes, relues toutes les 5 minutes."""
    stmt = select(DailyPrice.security_id, DailyPrice.date, DailyPrice.close, DailyPrice.volume).where(DailyPrice.date >= since)
    if security_ids is not None:
        stmt = stmt.where(DailyPrice.security_id.in_(security_ids))
    rows = session.execute(stmt.order_by(DailyPrice.security_id, DailyPrice.date))
    result: dict[int, list[Row]] = {}
    for row in rows:
        result.setdefault(row.security_id, []).append(row)
    return result


def incomplete_history_securities(session: Session) -> list[Security]:
    return list(session.scalars(
        select(Security).where(Security.active.is_(True), Security.history_complete.is_(False)).order_by(Security.id)
    ))


def mark_history_complete(session: Session, security_ids: list[int]) -> None:
    if security_ids:
        session.execute(update(Security).where(Security.id.in_(security_ids)).values(history_complete=True))


def first_price_dates(session: Session, security_ids: list[int]) -> dict[int, date]:
    rows = session.execute(
        select(DailyPrice.security_id, func.min(DailyPrice.date))
        .where(DailyPrice.security_id.in_(security_ids)).group_by(DailyPrice.security_id)
    )
    return {security_id: first for security_id, first in rows}


def price_date_range(session: Session, security_id: int) -> tuple[date | None, date | None]:
    first, last = session.execute(
        select(func.min(DailyPrice.date), func.max(DailyPrice.date)).where(DailyPrice.security_id == security_id)
    ).one()
    return first, last


def fundamentals_due(session: Session, share: int) -> list[tuple[int, str]]:
    """La part du jour des actions actives et cotées : jamais essayées d'abord, puis les plus anciennes.

    Chaque tentative, réussie ou non, est datée : un ticker que Yahoo ignore repasse en fin de file.
    Un titre sans aucun cours (inconnu de Yahoo) n'est pas demandé.
    """
    priced = select(SecurityQuote.security_id).where(SecurityQuote.security_id == Security.id).exists()
    rows = session.execute(
        select(Security.id, Security.yahoo_ticker)
        .where(Security.active.is_(True), Security.kind == "stock", priced)
        .order_by(Security.fundamentals_checked_at.asc().nulls_first(), Security.id)
    ).all()
    return [(sid, ticker) for sid, ticker in rows[:math.ceil(len(rows) / share)]]


def latest_price_dates(session: Session) -> dict[int, date]:
    rows = session.execute(select(DailyPrice.security_id, func.max(DailyPrice.date)).group_by(DailyPrice.security_id))
    return {security_id: last for security_id, last in rows}


def average_turnover(session: Session, since: date, days: int = 20) -> dict[int, float]:
    """Montant moyen échangé (cours × volume) sur les `days` dernières séances depuis `since`.

    `since` évite de relire tout l'historique (des dizaines de millions de lignes) à chaque palier.
    """
    ranked = select(
        DailyPrice.security_id,
        (DailyPrice.close * DailyPrice.volume).label("turnover"),
        func.row_number().over(partition_by=DailyPrice.security_id, order_by=DailyPrice.date.desc()).label("rn"),
    ).where(DailyPrice.date >= since).subquery()
    stmt = (
        select(ranked.c.security_id, func.avg(ranked.c.turnover))
        .where(ranked.c.rn <= days)
        .group_by(ranked.c.security_id)
    )
    return {security_id: float(value or 0.0) for security_id, value in session.execute(stmt)}


def upsert_fundamentals(session: Session, security_id: int, f: Fundamentals) -> None:
    record = session.get(SecurityFundamentals, security_id) or SecurityFundamentals(security_id=security_id)
    record.pe = f.pe
    record.eps = f.eps
    record.earnings_growth = f.earnings_growth
    record.revenue_growth = f.revenue_growth
    record.debt_to_equity = f.debt_to_equity
    record.profit_margin = f.profit_margin
    record.dividend_yield = f.dividend_yield
    record.market_cap = f.market_cap
    record.currency = f.currency
    # Effectif et CA bougent peu : une réponse Yahoo qui ne les donne pas ne doit pas effacer la valeur connue.
    record.employees = f.employees if f.employees is not None else record.employees
    if f.revenue is not None:
        record.revenue, record.revenue_currency = f.revenue, f.revenue_currency or f.currency
    record.updated_at = func.now()
    session.add(record)
