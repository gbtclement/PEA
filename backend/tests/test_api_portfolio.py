from datetime import UTC, date, datetime

import pytest

from app.jobs.tiers import tier_tickers
from app.models import DailyPrice, SecurityQuote
from tests.factories import make_security


def order(client, sid, side="buy", qty=10, price=50.0, day="2026-03-02", fee=None):
    body = {"security_id": sid, "trade_date": day, "side": side, "quantity": qty, "unit_price": price}
    if fee is not None:
        body["fee"] = fee
    assert client.post("/api/orders", json=body).status_code == 201


def quote(db, sid, price, previous):
    db.add(SecurityQuote(security_id=sid, price=price, previous_close=previous, change_pct=(price / previous - 1) * 100,
                         volume=1, as_of=datetime(2026, 3, 10, 16, 0, tzinfo=UTC)))
    db.flush()


def test_portfolio_empty(client):
    body = client.get("/api/portfolio").json()
    assert (body["total_value"], body["invested"], body["gain"], body["positions"], body["sectors"]) == (0, 0, 0, [], [])
    assert body["gain_pct"] is None and body["counter"]["count"] == 0
    assert client.get("/api/portfolio/history").json() == []


def test_portfolio_positions_values_and_day_change(client, db):
    lvmh = make_security(db, "MC.PA", name="LVMH")
    lvmh.sector = "Consumer Cyclical"
    total = make_security(db, "TTE.PA", name="TotalEnergies")
    total.sector = "Energy"
    order(client, lvmh.id, qty=10, price=50, fee=0)
    order(client, total.id, qty=5, price=100, fee=0)
    order(client, total.id, side="sell", qty=5, price=110, fee=0, day="2026-03-05")
    quote(db, lvmh.id, 60, 55)
    body = client.get("/api/portfolio").json()
    assert [p["symbol"] for p in body["positions"]] == ["MC"]
    p = body["positions"][0]
    assert (p["quantity"], p["avg_cost"], p["price"], p["value"], p["gain"], p["weight"]) == (10, 50.0, 60.0, 600.0, 100.0, 1.0)
    assert p["gain_pct"] == pytest.approx(20.0)
    assert (body["total_value"], body["invested"], body["gain"], body["realized_gain"]) == (600.0, 500.0, 100.0, 50.0)
    assert body["day_change"] == 50.0 and body["day_change_pct"] == pytest.approx(50 / 550 * 100, abs=0.01)
    assert body["sectors"] == [{"sector": "Consumer Cyclical", "value": 600.0, "weight": 1.0}]


def test_portfolio_position_without_price(client, db):
    s = make_security(db, "NEW.PA", name="Nouvelle")
    order(client, s.id, qty=4, price=25, fee=1)
    p = client.get("/api/portfolio").json()["positions"][0]
    assert p["price"] is None and p["value"] == 101.0 and p["gain"] == 0.0 and p["change_pct"] is None


def test_portfolio_uses_last_close_and_converts_nok(client, db):
    s = make_security(db, "NOKIA.OL", name="Nordic", market="Oslo Børs", country="NO")
    order(client, s.id, qty=10, price=8.5, fee=0)
    db.add(DailyPrice(security_id=s.id, date=date(2026, 3, 3), close=100.0))
    db.flush()
    p = client.get("/api/portfolio").json()["positions"][0]
    assert p["price"] == pytest.approx(8.5) and p["value"] == pytest.approx(85.0)


def test_portfolio_history_rebuilt_from_closes(client, db):
    s = make_security(db, "MC.PA")
    order(client, s.id, qty=2, price=10, fee=0, day="2026-03-02")
    for day, close in ((date(2026, 2, 27), 9.0), (date(2026, 3, 2), 10.0), (date(2026, 3, 3), 12.0)):
        db.add(DailyPrice(security_id=s.id, date=day, close=close))
    db.flush()
    points = client.get("/api/portfolio/history").json()
    assert [(p["date"], p["value"], p["invested"]) for p in points][:2] == [("2026-03-02", 20.0, 20.0), ("2026-03-03", 24.0, 20.0)]


def test_tier1_includes_held_securities(db, client):
    held = make_security(db, "HELD.PA")
    order(client, held.id, qty=1, price=10)
    assert "HELD.PA" in tier_tickers(db, 1, tier2_size=150)
