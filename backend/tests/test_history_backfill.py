from datetime import date

import pytest
from sqlalchemy import select

import app.jobs.market as market_module
from app.jobs.market import backfill_history
from app.models import DailyPrice, Security
from app.providers.base import DailyBar
from tests.factories import make_security
from tests.fakes import FakeMarket


def bar(day: date, close: float) -> DailyBar:
    return DailyBar(day, close, close, close, close, 10)


def store(db, security, day: date, close: float) -> None:
    db.add(DailyPrice(security_id=security.id, date=day, open=close, high=close, low=close, close=close, volume=1))
    db.flush()


def closes(db, security) -> list[tuple[date, float]]:
    return [tuple(row) for row in db.execute(
        select(DailyPrice.date, DailyPrice.close).where(DailyPrice.security_id == security.id).order_by(DailyPrice.date))]


def complete(db, security) -> bool:
    db.expire_all()
    return db.get(Security, security.id).history_complete


def test_backfill_adds_older_bars_and_marks_complete(db, make_ctx):
    security = make_security(db, "C.PA")
    make_security(db, "OLD.PA", active=False)
    store(db, security, date(2021, 1, 4), 50.0)
    market = FakeMarket(history={"C.PA": [bar(date(2000, 1, 3), 10.0), bar(date(2021, 1, 4), 50.0), bar(date(2021, 1, 5), 99.0)]})
    assert backfill_history(make_ctx(market=market)) == 1
    assert market.history_calls == [(["C.PA"], None)]
    # Seuls les cours antérieurs sont ajoutés ; les plus récents restent l'affaire du passage quotidien.
    assert closes(db, security) == [(date(2000, 1, 3), 10.0), (date(2021, 1, 4), 50.0)]
    assert complete(db, security) is True


def test_backfill_is_idempotent(db, make_ctx):
    security = make_security(db, "C.PA")
    store(db, security, date(2021, 1, 4), 50.0)
    market = FakeMarket(history={"C.PA": [bar(date(2000, 1, 3), 10.0), bar(date(2021, 1, 4), 50.0)]})
    ctx = make_ctx(market=market)
    backfill_history(ctx)
    assert backfill_history(ctx) == 0
    assert len(market.history_calls) == 1


def test_backfill_replaces_a_readjusted_series(db, make_ctx):
    security = make_security(db, "C.PA")
    store(db, security, date(2021, 1, 4), 50.0)
    store(db, security, date(2021, 1, 5), 52.0)
    # Yahoo a divisé l'action par deux depuis le premier chargement : la jonction ne colle plus.
    market = FakeMarket(history={"C.PA": [bar(date(2000, 1, 3), 5.0), bar(date(2021, 1, 4), 25.0), bar(date(2021, 1, 5), 26.0)]})
    backfill_history(make_ctx(market=market))
    assert closes(db, security) == [(date(2000, 1, 3), 5.0), (date(2021, 1, 4), 25.0), (date(2021, 1, 5), 26.0)]


def test_backfill_leaves_missing_tickers_for_next_run(db, make_ctx):
    found = make_security(db, "C.PA")
    missing = make_security(db, "X.PA")
    backfill_history(make_ctx(market=FakeMarket(history={"C.PA": [bar(date(2000, 1, 3), 10.0)]})))
    assert complete(db, found) is True
    assert complete(db, missing) is False


class FailsOnSecondCall(FakeMarket):
    def get_daily_history(self, tickers, start):
        if self.history_calls:
            raise ConnectionError("Yahoo KO")
        return super().get_daily_history(tickers, start)


def test_backfill_resumes_after_a_failure(db, make_ctx, monkeypatch):
    monkeypatch.setattr(market_module, "BACKFILL_BATCH", 1)
    first = make_security(db, "A.PA")
    second = make_security(db, "B.PA")
    history = {"A.PA": [bar(date(2000, 1, 3), 1.0)], "B.PA": [bar(date(2000, 1, 3), 2.0)]}
    with pytest.raises(ConnectionError):
        backfill_history(make_ctx(market=FailsOnSecondCall(history=history)))
    assert complete(db, first) is True and complete(db, second) is False
    market = FakeMarket(history=history)
    backfill_history(make_ctx(market=market))
    assert market.history_calls == [(["B.PA"], None)]
