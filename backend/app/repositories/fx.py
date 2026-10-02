from collections.abc import Callable
from contextlib import AbstractContextManager

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import FxRate


def save_rates(session: Session, rates: dict[str, float]) -> None:
    if not rates:
        return
    stmt = pg_insert(FxRate).values([{"currency": code, "rate_to_eur": rate} for code, rate in rates.items()])
    session.execute(stmt.on_conflict_do_update(
        index_elements=["currency"], set_={"rate_to_eur": stmt.excluded.rate_to_eur, "updated_at": func.now()},
    ))


def load_rates(session: Session) -> dict[str, float]:
    return {code: rate for code, rate in session.execute(select(FxRate.currency, FxRate.rate_to_eur))}


def store_loader(session_factory: Callable[[], AbstractContextManager[Session]]) -> Callable[[], dict[str, float]]:
    def load() -> dict[str, float]:
        with session_factory() as session:
            return load_rates(session)
    return load
