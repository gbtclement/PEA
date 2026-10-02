from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta

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


def test_backfill_writes_series_longer_than_the_bind_parameter_limit(db, make_ctx):
    security = make_security(db, "OLD.MI")
    store(db, security, date(2021, 1, 4), 50.0)
    long_series = [bar(date(1985, 1, 1) + timedelta(days=i), 1.0) for i in range(9500)]  # 7 paramètres par ligne
    assert backfill_history(make_ctx(market=FakeMarket(history={"OLD.MI": long_series}))) == 9500
    assert complete(db, security) is True


def test_backfill_checks_junction_on_first_common_date(db, make_ctx):
    security = make_security(db, "C.PA")
    store(db, security, date(2021, 1, 4), 50.0)
    store(db, security, date(2021, 1, 5), 52.0)
    # Yahoo n'a plus la séance du 04/01 : la comparaison se fait sur la première date commune (05/01).
    market = FakeMarket(history={"C.PA": [bar(date(2000, 1, 3), 5.0), bar(date(2021, 1, 5), 26.0)]})
    backfill_history(make_ctx(market=market))
    assert closes(db, security) == [(date(2000, 1, 3), 5.0), (date(2021, 1, 5), 26.0)]


def test_backfill_gives_up_on_dead_tickers_without_failing(db, make_ctx):
    dead = make_security(db, "GONE.PA")
    store(db, dead, date(2020, 3, 2), 3.0)  # plus coté depuis longtemps : Yahoo ne le renvoie plus
    alive = make_security(db, "LATE.PA")
    store(db, alive, date(2026, 9, 25), 3.0)
    now = datetime(2026, 9, 28, 20, 0, tzinfo=UTC)
    assert backfill_history(make_ctx(market=FakeMarket(), now=now)) == 0
    assert complete(db, dead) is True
    assert complete(db, alive) is False  # coté : on réessaiera


def test_backfill_skips_a_ticker_that_fails_to_save(db, make_ctx, monkeypatch):
    bad = make_security(db, "BAD.PA")
    good = make_security(db, "GOOD.PA")
    original = market_module.upsert_daily_bars

    def failing(session, security_id, bars):
        if security_id == bad.id:
            raise ValueError("ligne refusée")
        return original(session, security_id, bars)

    monkeypatch.setattr(market_module, "upsert_daily_bars", failing)
    history = {"BAD.PA": [bar(date(2000, 1, 3), 1.0)], "GOOD.PA": [bar(date(2000, 1, 3), 2.0)]}
    backfill_history(make_ctx(market=FakeMarket(history=history)))
    assert complete(db, good) is True and complete(db, bad) is False
    assert closes(db, good) == [(date(2000, 1, 3), 2.0)]


def test_backfill_takes_the_guard_per_batch(db, make_ctx, monkeypatch):
    monkeypatch.setattr(market_module, "BACKFILL_BATCH", 1)
    make_security(db, "A.PA")
    make_security(db, "B.PA")
    entered = []

    @contextmanager
    def guard():
        entered.append(1)
        yield

    history = {"A.PA": [bar(date(2000, 1, 3), 1.0)], "B.PA": [bar(date(2000, 1, 3), 2.0)]}
    backfill_history(make_ctx(market=FakeMarket(history=history)), guard=guard)
    assert len(entered) == 2


def test_backfill_loads_new_securities_entirely(db, make_ctx):
    new = make_security(db, "NEW.PA")
    backfill_history(make_ctx(market=FakeMarket(history={"NEW.PA": [bar(date(2000, 1, 3), 1.0), bar(date(2026, 10, 1), 2.0)]})))
    assert closes(db, new) == [(date(2000, 1, 3), 1.0), (date(2026, 10, 1), 2.0)]
    assert complete(db, new) is True


def test_backfill_gives_up_on_unknown_tickers_after_a_month(db, make_ctx):
    unknown = make_security(db, "RAW.DE")
    unknown.created_at = datetime(2026, 8, 1, tzinfo=UTC)
    recent = make_security(db, "LATE.DE")
    recent.created_at = datetime(2026, 9, 25, tzinfo=UTC)
    db.flush()
    backfill_history(make_ctx(market=FakeMarket(), now=datetime(2026, 9, 28, 20, 0, tzinfo=UTC)))
    assert complete(db, unknown) is True
    assert complete(db, recent) is False
