from datetime import UTC, date, datetime, timedelta

from app.models import DailyPrice, SecurityFundamentals, SecurityQuote
from app.providers.base import IntradayBar, NewsItem
from tests.factories import make_score, make_security

LAST = date(2026, 9, 25)


def with_history(db, days=300, start=100.0, step=1.0):
    security = make_security(db, "MC.PA", name="LVMH", isin="FR0000121014")
    for i in range(days):
        close = start + step * i
        db.add(DailyPrice(security_id=security.id, date=LAST - timedelta(days=days - 1 - i),
                          open=close, high=close, low=close, close=close, volume=10))
    db.flush()
    return security


def test_detail(client, db):
    security = with_history(db)
    db.add(SecurityFundamentals(security_id=security.id, pe=20.0, market_cap=3e11, currency="EUR"))
    make_score(db, security, total=75, components=[
        {"key": "trend", "label": "Tendance", "points": 20, "max_points": 20, "message": "✅", "group": "technical"}])
    body = client.get(f"/api/securities/{security.id}").json()
    assert body["name"] == "LVMH" and body["isin"] == "FR0000121014"
    assert body["fundamentals"]["pe"] == 20.0
    assert body["score_detail"]["total"] == 75
    assert body["score_detail"]["components"][0]["key"] == "trend"


def test_security_detail_404(client):
    assert client.get("/api/securities/999999").status_code == 404


def test_security_page_without_score(client, db):
    security = make_security(db, "NEW.PA")
    body = client.get(f"/api/securities/{security.id}").json()
    assert body["score_detail"] is None and body["fundamentals"] is None and body["price"] is None


def test_history_daily_with_indicators(client, db):
    security = with_history(db)
    body = client.get(f"/api/securities/{security.id}/history", params={"period": "1M"}).json()
    assert body["intraday"] is False
    assert body["bars"][-1]["time"] == "2026-09-25"
    assert 20 <= len(body["bars"]) <= 32
    assert len(body["sma200"]) == len(body["bars"])  # 300 séances : la moyenne 200 jours existe sur tout le mois
    assert body["rsi"][-1]["value"] == 100.0
    assert set(body["macd"][-1]) == {"time", "macd", "signal", "histogram"}
    assert body["interval"] == "day" and body["first_date"] == "2025-11-30" and body["last_date"] == "2026-09-25"


def get_history(client, security, **params):
    return client.get(f"/api/securities/{security.id}/history", params=params)


def test_history_5y_keeps_five_years(client, db):
    security = with_history(db, days=2000)
    body = get_history(client, security, period="5Y").json()
    assert len(body["bars"]) == 365 * 5 + 2  # 5 ans + 1 jour en arrière, jour de départ inclus
    max_body = get_history(client, security, period="MAX").json()
    assert len(max_body["bars"]) == 2000 and max_body["interval"] == "day"


def test_history_10y_groups_by_week(client, db):
    security = with_history(db, days=3700)
    body = get_history(client, security, period="10Y").json()
    assert body["interval"] == "week"
    times = [b["time"] for b in body["bars"]]
    assert 520 <= len(times) <= 524 and times == sorted(set(times))
    assert body["bars"][-1]["close"] == 100.0 + 3699  # dernière clôture de la dernière semaine
    for line in ("sma50", "sma200", "rsi"):
        assert {p["time"] for p in body[line]} <= set(times)
    assert {p["time"] for p in body["macd"]} <= set(times)


def test_history_max_groups_by_month_beyond_ten_years(client, db):
    security = with_history(db, days=4000)
    body = get_history(client, security, period="MAX").json()
    assert body["interval"] == "month"
    last = body["bars"][-1]
    assert last["time"] == "2026-09-01"
    assert last["volume"] == 10 * 25 and last["high"] == 100.0 + 3999 and last["open"] == 100.0 + 3999 - 24
    assert body["first_date"] == (LAST - timedelta(days=3999)).isoformat()


def test_history_custom_range(client, db):
    security = with_history(db)
    body = get_history(client, security, period="custom", start="2026-09-01", end="2026-09-10").json()
    assert [b["time"] for b in body["bars"]][0] == "2026-09-01" and body["bars"][-1]["time"] == "2026-09-10"
    assert len(body["bars"]) == 10 and body["interval"] == "day"
    assert len(body["sma200"]) == 10  # indicateurs calculés sur tout l'historique, puis coupés


def test_history_custom_range_requires_ordered_dates(client, db):
    security = with_history(db)
    assert get_history(client, security, period="custom", start="2026-09-01").status_code == 422
    assert get_history(client, security, period="custom", start="2026-09-10", end="2026-09-01").status_code == 422


def test_history_custom_range_outside_history(client, db):
    security = with_history(db)
    response = get_history(client, security, period="custom", start="1990-01-01", end="1990-12-31")
    assert response.status_code == 200 and response.json()["bars"] == []


def test_history_intraday(client, db, fake_market):
    security = with_history(db)
    moment = datetime(2026, 9, 25, 7, 0, tzinfo=UTC)
    fake_market.intraday["MC.PA"] = [IntradayBar(moment, 1, 2, 0.5, 1.5, 10)]
    body = client.get(f"/api/securities/{security.id}/history", params={"period": "1D"}).json()
    assert body["intraday"] is True
    assert body["bars"] == [{"time": int(moment.timestamp()), "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10}]
    assert fake_market.intraday_calls == [("MC.PA", "1d", "5m")]
    client.get(f"/api/securities/{security.id}/history", params={"period": "1D"})
    assert len(fake_market.intraday_calls) == 1  # servi par le cache


def test_history_intraday_provider_failure(client, db, fake_market):
    security = with_history(db)
    fake_market.fail_on_demand = True
    response = client.get(f"/api/securities/{security.id}/history", params={"period": "1W"})
    assert response.status_code == 200 and response.json()["bars"] == []


def test_history_invalid_period(client, db):
    security = with_history(db)
    assert client.get(f"/api/securities/{security.id}/history", params={"period": "2Y"}).status_code == 422


def test_news(client, db, fake_market):
    security = with_history(db)
    fake_market.news["MC.PA"] = [NewsItem("Titre", "https://ex.com", "Reuters", None)]
    assert client.get(f"/api/securities/{security.id}/news").json() == [
        {"title": "Titre", "url": "https://ex.com", "publisher": "Reuters", "published_at": None}]


def test_news_provider_failure(client, db, fake_market):
    security = with_history(db)
    fake_market.fail_on_demand = True
    response = client.get(f"/api/securities/{security.id}/news")
    assert response.status_code == 200 and response.json() == []


def test_simulate(client, db):
    security = with_history(db)  # le 25/09 : 399 € ; un mois avant (25/08) : 368 €
    db.add(SecurityQuote(security_id=security.id, price=400.0, previous_close=399, change_pct=0.25, volume=1,
                         as_of=datetime(2026, 9, 28, 8, 0, tzinfo=UTC)))
    db.flush()
    body = client.get(f"/api/securities/{security.id}/simulate", params={"amount": 1000, "period": "1M"}).json()
    assert body["start_date"] == "2026-08-25" and body["start_price"] == 368.0
    assert body["shares"] == 2 and body["invested"] == 736.0
    assert body["buy_fee"] == 1.32 and body["current_value"] == 800.0 and body["sell_fee"] == 1.44
    assert body["gain"] == 61.24
    assert body["message"] is None


def test_simulate_amount_below_price(client, db):
    security = with_history(db)
    body = client.get(f"/api/securities/{security.id}/simulate", params={"amount": 50, "period": "1M"}).json()
    assert body["shares"] == 0 and body["gain"] == 0
    assert "ne permet pas" in body["message"]


def test_simulate_rejects_non_positive_amount(client, db):
    security = with_history(db)
    for amount in (0, -100):
        assert client.get(f"/api/securities/{security.id}/simulate", params={"amount": amount, "period": "1M"}).status_code == 422


def test_simulate_without_history(client, db):
    security = make_security(db, "NEW.PA")
    body = client.get(f"/api/securities/{security.id}/simulate", params={"amount": 500, "period": "1Y"}).json()
    assert body["shares"] == 0 and "historique" in body["message"]


def test_fee_estimate(client):
    assert client.get("/api/fees/estimate", params={"amount": 400}).json() == {"amount": 400.0, "fee": 1.92, "rate": 0.0048}
    assert client.get("/api/fees/estimate", params={"amount": -1}).status_code == 422
