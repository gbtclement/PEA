from collections import defaultdict
from datetime import date

import pandas as pd
from sqlalchemy import func, select
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


def stock_series(session: Session, since: date) -> dict[int, pd.DataFrame]:
    """Clôtures et volumes des actions actives depuis `since` : {security_id: DataFrame(close, volume)}."""
    rows = session.execute(
        select(DailyPrice.security_id, DailyPrice.date, DailyPrice.close, DailyPrice.volume)
        .join(Security, Security.id == DailyPrice.security_id)
        .where(Security.kind == "stock", Security.active.is_(True), DailyPrice.date >= since)
        .order_by(DailyPrice.security_id, DailyPrice.date)
    ).all()
    if not rows:
        return {}
    frame = pd.DataFrame(rows, columns=["security_id", "date", "close", "volume"])
    frame["date"] = pd.to_datetime(frame["date"])
    return {sid: group.set_index("date")[["close", "volume"]].astype(float) for sid, group in frame.groupby("security_id")}


def index_closes(session: Session, since: date) -> pd.Series:
    rows = session.execute(
        select(DailyPrice.date, DailyPrice.close).join(Security, Security.id == DailyPrice.security_id)
        .where(Security.yahoo_ticker == INDEX_TICKER, DailyPrice.date >= since).order_by(DailyPrice.date)
    ).all()
    return pd.Series([r.close for r in rows], index=pd.to_datetime([r.date for r in rows]), dtype=float)


def upsert_forecasts(session: Session, rows: list[dict]) -> int:
    if not rows:
        return 0
    stmt = pg_insert(Forecast).values(rows)
    session.execute(stmt.on_conflict_do_update(
        constraint="uq_forecast_security_day_horizon",
        set_={k: stmt.excluded[k] for k in ("expected_return", "prob_up", "reliability", "signals", "rank", "base_close")},
    ))
    return len(rows)


def pending_forecasts(session: Session) -> dict[int, list[Forecast]]:
    by_security: dict[int, list[Forecast]] = defaultdict(list)
    for f in session.scalars(select(Forecast).where(Forecast.actual_return.is_(None))):
        by_security[f.security_id].append(f)
    return by_security


def closes_after(session: Session, security_id: int, after: date) -> list[tuple[date, float]]:
    rows = session.execute(
        select(DailyPrice.date, DailyPrice.close)
        .where(DailyPrice.security_id == security_id, DailyPrice.date > after).order_by(DailyPrice.date)
    ).all()
    return [(r.date, r.close) for r in rows]
