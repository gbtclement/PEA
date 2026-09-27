from collections import defaultdict
from datetime import date

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import DailyPrice, Forecast, ForecastRun, Security

INDEX_TICKER = "^FCHI"


def latest_run(session: Session) -> ForecastRun | None:
    return session.scalars(select(ForecastRun).order_by(ForecastRun.computed_at.desc(), ForecastRun.id.desc()).limit(1)).first()


def latest_as_of(session: Session) -> date | None:
    return session.scalar(select(func.max(Forecast.as_of)))


def forecasts_for(session: Session, as_of: date) -> list[Forecast]:
    return list(session.scalars(select(Forecast).where(Forecast.as_of == as_of)))


def stock_series(session: Session, since: date, *, include_inactive: bool = False) -> dict[int, pd.DataFrame]:
    """Clôtures et volumes des actions depuis `since` : {security_id: DataFrame(close, volume)}.

    `include_inactive` garde les titres qui ne sont plus cotés : sans eux, les statistiques ne verraient que les
    entreprises qui ont survécu, ce qui embellirait les résultats.
    """
    conditions = [Security.kind == "stock", DailyPrice.date >= since]
    if not include_inactive:
        conditions.append(Security.active.is_(True))
    rows = session.execute(
        select(DailyPrice.security_id, DailyPrice.date, DailyPrice.close, DailyPrice.volume)
        .join(Security, Security.id == DailyPrice.security_id)
        .where(*conditions)
        .order_by(DailyPrice.security_id, DailyPrice.date)
    ).all()
    if not rows:
        return {}
    frame = pd.DataFrame(rows, columns=["security_id", "date", "close", "volume"])
    frame["date"] = pd.to_datetime(frame["date"])
    return {sid: group.set_index("date")[["close", "volume"]].astype(float) for sid, group in frame.groupby("security_id")}


def stock_markets(session: Session) -> dict[int, str]:
    """Place de cotation de chaque action, pour en déduire la devise : {security_id: marché}."""
    return dict(session.execute(select(Security.id, Security.market).where(Security.kind == "stock")).all())


def index_closes(session: Session, since: date) -> pd.Series:
    rows = session.execute(
        select(DailyPrice.date, DailyPrice.close).join(Security, Security.id == DailyPrice.security_id)
        .where(Security.yahoo_ticker == INDEX_TICKER, DailyPrice.date >= since).order_by(DailyPrice.date)
    ).all()
    return pd.Series([r.close for r in rows], index=pd.to_datetime([r.date for r in rows]), dtype=float)


def replace_forecasts(session: Session, as_of: date, rows: list[dict]) -> int:
    """Remplace les prédictions (non vérifiées) du jour `as_of` : un nouveau calcul le même jour ne laisse rien de périmé."""
    session.execute(delete(Forecast).where(Forecast.as_of == as_of, Forecast.actual_return.is_(None)))
    for start in range(0, len(rows), 1_000):  # par paquets : limite du nombre de paramètres d'une requête
        session.execute(pg_insert(Forecast).values(rows[start:start + 1_000]).on_conflict_do_nothing())
    return len(rows)


def pending_forecasts(session: Session) -> dict[int, list[Forecast]]:
    by_security: dict[int, list[Forecast]] = defaultdict(list)
    for f in session.scalars(select(Forecast).where(Forecast.actual_return.is_(None))):
        by_security[f.security_id].append(f)
    return by_security


def closes_between(session: Session, security_ids: list[int], start: date, end: date) -> dict[int, list[tuple[date, float]]]:
    """Clôtures stockées de `start` à `end` inclus, pour plusieurs titres en une requête."""
    rows = session.execute(
        select(DailyPrice.security_id, DailyPrice.date, DailyPrice.close)
        .where(DailyPrice.security_id.in_(security_ids), DailyPrice.date >= start, DailyPrice.date <= end)
        .order_by(DailyPrice.security_id, DailyPrice.date)
    ).all()
    out: dict[int, list[tuple[date, float]]] = defaultdict(list)
    for r in rows:
        out[r.security_id].append((r.date, r.close))
    return out
