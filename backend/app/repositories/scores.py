from statistics import median

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Favorite, PriceAlert, SecurityScore


def upsert_score(session: Session, security_id: int, values: dict) -> None:
    row = {"security_id": security_id, **values}
    stmt = pg_insert(SecurityScore).values(row)
    session.execute(stmt.on_conflict_do_update(
        index_elements=["security_id"], set_={k: stmt.excluded[k] for k in values},
    ))


def top_security_ids(session: Session, limit: int) -> list[int]:
    stmt = (
        select(SecurityScore.security_id)
        .where(SecurityScore.eligible_for_top.is_(True))
        .order_by(SecurityScore.total.desc(), SecurityScore.avg_turnover_eur.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt))


def favorite_security_ids(session: Session) -> set[int]:
    return set(session.scalars(select(Favorite.security_id)))


def sector_median_pe(pe_by_sector: dict[str | None, list[float]]) -> dict[str | None, float]:
    """Médiane des PER positifs par secteur (au moins 3 valeurs) ; la clé None porte la médiane globale."""
    everything = [pe for values in pe_by_sector.values() for pe in values]
    medians: dict[str | None, float] = {}
    if everything:
        medians[None] = median(everything)
    for sector, values in pe_by_sector.items():
        if sector is not None and len(values) >= 3:
            medians[sector] = median(values)
    return medians


def alert_security_ids(session: Session) -> set[int]:
    return set(session.scalars(select(PriceAlert.security_id).where(PriceAlert.active.is_(True))))
