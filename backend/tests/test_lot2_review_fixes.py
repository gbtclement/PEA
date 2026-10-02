from datetime import UTC, date, datetime, timedelta

from app.jobs.scoring import refresh_scores
from app.models import DailyPrice, SecurityFundamentals, SecurityQuote, SecurityScore, UserSettings
from app.repositories.market_data import daily_series
from app.repositories.screener import screener_rows
from tests.factories import make_score, make_security

NOW = datetime(2026, 9, 28, 8, 0, tzinfo=UTC)
LAST = date(2026, 9, 25)


def add_prices(db, security, days=300, start=100.0, step=1.0):
    for i in range(days):
        close = start + step * i
        db.add(DailyPrice(security_id=security.id, date=LAST - timedelta(days=days - 1 - i),
                          open=close, high=close, low=close, close=close, volume=10_000))
    db.flush()


def test_pea_user_does_not_see_a_non_pea_security_in_the_top(client, db, user):
    excluded = make_security(db, "TTE.PA", eligibility="non_eligible")
    kept = make_security(db, "MC.PA")
    make_score(db, excluded, total=99, eligible_for_top=True)
    make_score(db, kept, total=80, eligible_for_top=True)
    db.merge(UserSettings(user_id=user.id, envelopes=["pea"]))
    db.flush()
    assert [t["symbol"] for t in client.get("/api/rankings/top").json()] == ["MC"]


def test_scores_job_clears_stale_top_flag(db, make_ctx):
    excluded = make_security(db, "TTE.PA", active=False)
    make_score(db, excluded, total=99, eligible_for_top=True)
    refresh_scores(make_ctx(now=NOW))
    stale = db.get(SecurityScore, excluded.id)
    db.refresh(stale)
    assert stale.eligible_for_top is False


def test_daily_series_returns_light_rows(db):
    security = make_security(db, "MC.PA")
    add_prices(db, security, days=3)
    rows = daily_series(db, LAST - timedelta(days=10))[security.id]
    assert not isinstance(rows[0], DailyPrice)
    assert (rows[-1].date, rows[-1].close, rows[-1].volume) == (LAST, 102.0, 10_000)


def test_screener_rows_by_id_includes_indices(db, user):
    index = make_security(db, "^FCHI", kind="index", eligibility="non_eligible", country=None)
    make_security(db, "MC.PA")
    rows = screener_rows(db, user.id, security_id=index.id)
    assert [r[0].id for r in rows] == [index.id]


def test_simulate_converts_nok_prices(client, db):
    oslo = make_security(db, "X.OL", market="Oslo Børs", country="NO")
    add_prices(db, oslo, days=40, start=700.0, step=0.0)  # 700 NOK ≈ 59,5 €
    body = client.get(f"/api/securities/{oslo.id}/simulate", params={"amount": 500, "period": "1M"}).json()
    assert body["message"] is None
    assert body["shares"] == 8
    assert body["start_price"] == 59.5


def test_detail_exposes_currency(client, db):
    oslo = make_security(db, "X.OL", market="Oslo Børs", country="NO")
    paris = make_security(db, "MC.PA")
    assert client.get(f"/api/securities/{oslo.id}").json()["currency"] == "NOK"
    assert client.get(f"/api/securities/{paris.id}").json()["currency"] == "EUR"


def test_screener_exposes_isin_and_ratio(client, db):
    security = make_security(db, "MC.PA", isin="FR0000121014")
    make_score(db, security, available_ratio=0.6)
    row = client.get("/api/screener").json()[0]
    assert row["isin"] == "FR0000121014"
    assert row["available_ratio"] == 0.6


def test_empty_fundamentals_row_is_not_no_dividend(db, make_ctx):
    security = make_security(db, "A.PA")
    add_prices(db, security)
    db.add(SecurityFundamentals(security_id=security.id))
    db.flush()
    refresh_scores(make_ctx(now=NOW))
    keys = {c["key"] for c in db.get(SecurityScore, security.id).components}
    assert "dividend" not in keys


def test_eligibility_update_uses_current_user(admin_client, db):
    security = make_security(db, "MC.PA")
    assert admin_client.patch(f"/api/securities/{security.id}/eligibility", json={"override": "eligible"}).status_code == 200
