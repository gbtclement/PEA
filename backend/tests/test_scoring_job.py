from datetime import UTC, date, datetime, timedelta

from app.core.current_user import ensure_default_user
from app.jobs.scheduler import quotes_job
from app.jobs.scoring import refresh_scores
from app.jobs.tiers import tier_tickers
from app.models import DailyPrice, DataStatus, Favorite, SecurityFundamentals, SecurityQuote, SecurityScore
from app.providers.base import Quote
from tests.factories import make_score, make_security
from tests.fakes import FakeMarket

NOW = datetime(2026, 9, 28, 8, 0, tzinfo=UTC)  # lundi 10h à Paris
LAST_DAY = date(2026, 9, 25)


def add_series(db, security, days: int, start: float = 100.0, step: float = 0.5, volume: int = 10_000) -> None:
    for i in range(days):
        day = LAST_DAY - timedelta(days=days - 1 - i)
        close = start + step * i
        db.add(DailyPrice(security_id=security.id, date=day, open=close, high=close, low=close, close=close, volume=volume))
    db.flush()


def add_fundamentals(db, security, **fields) -> None:
    values = dict(pe=10.0, eps=2.0, earnings_growth=0.2, revenue_growth=0.2, debt_to_equity=0.3,
                  profit_margin=0.15, dividend_yield=0.04, market_cap=1e10, currency="EUR")
    values.update(fields)
    db.add(SecurityFundamentals(security_id=security.id, **values))
    db.flush()


def setup_market(db):
    cac = make_security(db, "^FCHI", kind="index", eligibility="non_eligible", country=None)
    add_series(db, cac, 260, start=7000, step=1)
    return cac


def test_scores_liquid_stock_enters_top(db, make_ctx):
    setup_market(db)
    stock = make_security(db, "A.PA")
    add_series(db, stock, 260)
    add_fundamentals(db, stock)
    refresh_scores(make_ctx(now=NOW))
    score = db.get(SecurityScore, stock.id)
    assert score.total is not None and score.total > 50
    assert score.liquid is True and score.history_days == 260
    assert score.eligible_for_top is True
    assert score.perf_1w is not None and score.perf_1y is not None
    assert len(score.sparkline) == 63
    assert {c["key"] for c in score.components} >= {"trend", "valuation"}


def test_scores_illiquid_or_short_history_excluded_from_top(db, make_ctx):
    setup_market(db)
    illiquid = make_security(db, "B.PA")
    add_series(db, illiquid, 260, volume=10)
    young = make_security(db, "C.PA")
    add_series(db, young, 50)
    refresh_scores(make_ctx(now=NOW))
    assert db.get(SecurityScore, illiquid.id).eligible_for_top is False
    assert db.get(SecurityScore, illiquid.id).liquid is False
    assert db.get(SecurityScore, young.id).eligible_for_top is False


def test_scores_convert_nok_turnover(db, make_ctx):
    setup_market(db)
    oslo = make_security(db, "X.OL", market="Oslo Børs", country="NO")
    add_series(db, oslo, 260, start=100, step=0, volume=10_000)  # 1 M NOK ≈ 85 000 €
    refresh_scores(make_ctx(now=NOW))
    assert db.get(SecurityScore, oslo.id).liquid is False


def test_scores_etf_has_no_fundamental(db, make_ctx):
    setup_market(db)
    etf = make_security(db, "CW8.PA", kind="etf")
    add_series(db, etf, 260)
    refresh_scores(make_ctx(now=NOW))
    score = db.get(SecurityScore, etf.id)
    assert score.fundamental is None and score.eligible_for_top is False
    assert score.available_ratio == 1.0


def test_scores_use_newer_quote(db, make_ctx):
    setup_market(db)
    stock = make_security(db, "A.PA")
    add_series(db, stock, 260)
    db.add(SecurityQuote(security_id=stock.id, price=500.0, previous_close=229.5, change_pct=100.0, volume=1, as_of=NOW))
    db.flush()
    refresh_scores(make_ctx(now=NOW))
    assert db.get(SecurityScore, stock.id).sparkline[-1] == 500.0


def test_scores_handle_missing_data(db, make_ctx):
    stock = make_security(db, "EMPTY.PA")
    refresh_scores(make_ctx(now=NOW))
    score = db.get(SecurityScore, stock.id)
    assert score.total is None and score.eligible_for_top is False and score.sparkline == []


def test_no_dividend_counts_as_zero_when_fundamentals_known(db, make_ctx):
    setup_market(db)
    stock = make_security(db, "A.PA")
    add_series(db, stock, 260)
    add_fundamentals(db, stock, dividend_yield=None)
    refresh_scores(make_ctx(now=NOW))
    dividend = next(c for c in db.get(SecurityScore, stock.id).components if c["key"] == "dividend")
    assert dividend["points"] == 0


def test_tier1_includes_favorites_and_top(db):
    user = ensure_default_user(db)
    make_security(db, "^FCHI", kind="index", eligibility="non_eligible", country=None)
    fav = make_security(db, "FAV.PA")
    top = make_security(db, "TOP.PA")
    other = make_security(db, "OTH.PA")
    db.add(Favorite(user_id=user.id, security_id=fav.id))
    make_score(db, top, total=90, eligible_for_top=True)
    make_score(db, other, total=10, eligible_for_top=False)
    db.flush()
    assert tier_tickers(db, 1, tier2_size=10) == ["FAV.PA", "TOP.PA", "^FCHI"]
    assert "FAV.PA" not in tier_tickers(db, 2, tier2_size=10)


def test_quotes_job_tier2_triggers_scores(db, make_ctx):
    make_security(db, "A.PA")
    market = FakeMarket(quotes={"A.PA": Quote(10.0, 9.0, 11.1, 1, NOW)})
    quotes_job(make_ctx(market=market, now=NOW), 2)
    assert db.get(DataStatus, "scores") is not None
