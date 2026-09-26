from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.services.market_calendar import PARIS

from app.jobs.market import refresh_daily_history, refresh_fundamentals, refresh_quotes
from app.models import DailyPrice, Security, SecurityFundamentals, SecurityQuote
from app.providers.base import DailyBar, Fundamentals, Quote
from tests.factories import make_security
from tests.fakes import FakeMarket

NOW = datetime(2026, 9, 28, 8, 0, tzinfo=UTC)


def quote(price: float) -> Quote:
    return Quote(price=price, previous_close=price - 1, change_pct=1.0, volume=10, as_of=NOW)


def add_prices(db, security, close: float, volume: int, days: int = 20) -> None:
    for i in range(days):
        db.add(DailyPrice(security_id=security.id, date=date(2026, 9, 25) - timedelta(days=i),
                          open=close, high=close, low=close, close=close, volume=volume))
    db.flush()


def setup_universe(db):
    index = make_security(db, "^FCHI", kind="index", eligibility="non_eligible", country=None)
    liquid = make_security(db, "A.PA")
    illiquid = make_security(db, "B.PA")
    excluded = make_security(db, "US.PA", eligibility="non_eligible", country="US")
    inactive = make_security(db, "OLD.PA", active=False)
    add_prices(db, liquid, 100.0, 10_000)
    add_prices(db, illiquid, 10.0, 100)
    return index, liquid, illiquid, excluded, inactive


def fundamentals(industry: str | None = "Luxury Goods") -> Fundamentals:
    return Fundamentals(pe=15.0, eps=2.0, earnings_growth=0.1, revenue_growth=0.05, debt_to_equity=0.4,
                        profit_margin=0.12, dividend_yield=0.03, market_cap=1e10, sector="Consumer",
                        industry=industry, currency="EUR")


def test_quote_tiers(db, make_ctx):
    setup_universe(db)
    market = FakeMarket(quotes={t: quote(10) for t in ["^FCHI", "A.PA", "B.PA", "US.PA", "OLD.PA"]})
    ctx = make_ctx(market=market, now=NOW, tier2_size=1)
    refresh_quotes(ctx, 1)
    refresh_quotes(ctx, 2)
    refresh_quotes(ctx, 3)
    assert market.quote_calls == [["^FCHI"], ["A.PA"], ["B.PA"]]


def test_refresh_quotes_stores_prices(db, make_ctx):
    _, liquid, *_ = setup_universe(db)
    ctx = make_ctx(market=FakeMarket(quotes={"A.PA": quote(123.4)}), now=NOW, tier2_size=10)
    assert refresh_quotes(ctx, 2) == 1
    assert db.get(SecurityQuote, liquid.id).price == 123.4
    ctx.market.quotes["A.PA"] = quote(130.0)
    refresh_quotes(ctx, 2)
    assert db.get(SecurityQuote, liquid.id).price == 130.0


def test_refresh_quotes_ignores_missing_tickers(db, make_ctx):
    setup_universe(db)
    ctx = make_ctx(market=FakeMarket(quotes={"A.PA": quote(10)}), now=NOW, tier2_size=10)
    assert refresh_quotes(ctx, 2) == 1  # B.PA absent de la réponse : ignoré


def test_refresh_quotes_raises_on_total_outage(db, make_ctx):
    setup_universe(db)
    ctx = make_ctx(market=FakeMarket(quotes={}), now=NOW, tier2_size=10)
    with pytest.raises(RuntimeError):
        refresh_quotes(ctx, 2)


def test_history_raises_on_total_outage(db, make_ctx):
    make_security(db, "C.PA")
    with pytest.raises(RuntimeError):
        refresh_daily_history(make_ctx(market=FakeMarket(history={}), now=NOW))


def test_history_writes_closing_quote(db, make_ctx):
    security = make_security(db, "C.PA")
    intraday = datetime(2026, 9, 25, 15, 10, tzinfo=UTC)  # 17h10 à Paris
    db.add(SecurityQuote(security_id=security.id, price=1.5, previous_close=1.0, change_pct=50.0, volume=1, as_of=intraday))
    db.flush()
    bars = [DailyBar(date(2026, 9, 24), 1, 1, 1, 1.0, 10), DailyBar(date(2026, 9, 25), 1, 1, 1, 2.0, 10)]
    refresh_daily_history(make_ctx(market=FakeMarket(history={"C.PA": bars}), now=NOW))
    stored = db.get(SecurityQuote, security.id)
    db.refresh(stored)
    assert stored.price == 2.0
    assert stored.previous_close == 1.0
    assert stored.change_pct == pytest.approx(100.0)
    assert stored.as_of == datetime(2026, 9, 25, 17, 35, tzinfo=PARIS)


def test_history_keeps_newer_live_quote(db, make_ctx):
    security = make_security(db, "C.PA")
    live = datetime(2026, 9, 28, 8, 0, tzinfo=UTC)
    db.add(SecurityQuote(security_id=security.id, price=3.0, previous_close=2.0, change_pct=50.0, volume=1, as_of=live))
    db.flush()
    bars = [DailyBar(date(2026, 9, 24), 1, 1, 1, 1.0, 10), DailyBar(date(2026, 9, 25), 1, 1, 1, 2.0, 10)]
    refresh_daily_history(make_ctx(market=FakeMarket(history={"C.PA": bars}), now=NOW))
    stored = db.get(SecurityQuote, security.id)
    db.refresh(stored)
    assert stored.price == 3.0


class SplitMarket(FakeMarket):
    """Après une division par 10, Yahoo renvoie tout l'historique ajusté."""

    def get_daily_history(self, tickers, start):
        self.history_calls.append((list(tickers), start))
        if start == date(2026, 9, 25):
            return {"C.PA": [DailyBar(date(2026, 9, 25), 10, 10, 10, 10.0, 10)]}
        return {"C.PA": [DailyBar(date(2026, 9, 24), 9, 9, 9, 9.0, 10), DailyBar(date(2026, 9, 25), 10, 10, 10, 10.0, 10)]}


def test_history_reloads_after_split(db, make_ctx):
    security = make_security(db, "C.PA")
    db.add(DailyPrice(security_id=security.id, date=date(2026, 9, 24), open=90, high=90, low=90, close=90.0, volume=1))
    db.add(DailyPrice(security_id=security.id, date=date(2026, 9, 25), open=100, high=100, low=100, close=100.0, volume=1))
    db.flush()
    market = SplitMarket()
    refresh_daily_history(make_ctx(market=market, now=NOW))
    assert market.history_calls[-1] == (["C.PA"], date(2026, 9, 28) - timedelta(days=365 * 5))
    closes = db.scalars(select(DailyPrice.close).where(DailyPrice.security_id == security.id).order_by(DailyPrice.date)).all()
    assert closes == [9.0, 10.0]


def test_fundamentals_without_industry_keep_known_one(db, make_ctx):
    stock = make_security(db, "GFC.PA")
    stock.industry = "REIT - Office"
    stock.eligibility = "a_verifier"
    db.flush()
    market = FakeMarket(fundamentals={"GFC.PA": fundamentals(industry=None)})
    refresh_fundamentals(make_ctx(market=market, now=NOW))
    refreshed = db.get(Security, stock.id)
    assert (refreshed.industry, refreshed.eligibility) == ("REIT - Office", "a_verifier")


def test_history_backfill_then_incremental(db, make_ctx):
    security = make_security(db, "C.PA")
    bars = [DailyBar(date(2026, 9, 24), 1, 1, 1, 1.0, 10), DailyBar(date(2026, 9, 25), 1, 1, 1, 2.0, 10)]
    market = FakeMarket(history={"C.PA": bars})
    ctx = make_ctx(market=market, now=NOW)
    refresh_daily_history(ctx)
    assert market.history_calls[0] == (["C.PA"], date(2026, 9, 28) - timedelta(days=365 * 5))
    refresh_daily_history(ctx)
    assert market.history_calls[1] == (["C.PA"], date(2026, 9, 25))
    count = db.scalar(select(func.count()).select_from(DailyPrice).where(DailyPrice.security_id == security.id))
    assert count == 2


def test_history_skips_non_eligible(db, make_ctx):
    make_security(db, "US.PA", eligibility="non_eligible", country="US")
    market = FakeMarket()
    refresh_daily_history(make_ctx(market=market, now=NOW))
    assert all("US.PA" not in tickers for tickers, _ in market.history_calls)


def test_fundamentals_store_and_reclassify(db, make_ctx):
    stock = make_security(db, "GFC.PA")
    etf = make_security(db, "CW8.PA", kind="etf")
    market = FakeMarket(fundamentals={"GFC.PA": fundamentals(industry="REIT - Office")})
    assert refresh_fundamentals(make_ctx(market=market, now=NOW)) == 1
    assert market.fundamental_calls == ["GFC.PA"]  # pas d'ETF
    assert db.get(SecurityFundamentals, stock.id).pe == 15.0
    refreshed = db.get(Security, stock.id)
    assert (refreshed.industry, refreshed.eligibility) == ("REIT - Office", "a_verifier")
    assert db.get(Security, etf.id).eligibility == "eligible"


def test_fundamentals_keep_override(db, make_ctx):
    stock = make_security(db, "GFC.PA")
    stock.eligibility_override = "eligible"
    db.flush()
    market = FakeMarket(fundamentals={"GFC.PA": fundamentals(industry="REIT - Office")})
    refresh_fundamentals(make_ctx(market=market, now=NOW))
    refreshed = db.get(Security, stock.id)
    assert (refreshed.eligibility, refreshed.eligibility_source) == ("eligible", "override")
