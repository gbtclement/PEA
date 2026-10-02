from datetime import UTC, datetime

from app.models import Favorite, SecurityFundamentals, SecurityQuote
from tests.factories import make_score, make_security

AS_OF = datetime(2026, 9, 25, 15, 35, tzinfo=UTC)


def quote(db, security, price, change):
    db.add(SecurityQuote(security_id=security.id, price=price, previous_close=price, change_pct=change, volume=1, as_of=AS_OF))


def seed(db, user):
    lvmh = make_security(db, "MC.PA", name="LVMH")
    total = make_security(db, "TTE.PA", name="TotalEnergies")
    small = make_security(db, "SMA.PA", name="Petite")
    etf = make_security(db, "CW8.PA", name="Amundi World", kind="etf")
    make_security(db, "^FCHI", name="CAC 40", kind="index", eligibility="non_eligible", country=None)
    quote(db, lvmh, 600, 2.5)
    quote(db, total, 60, -1.5)
    quote(db, small, 5, 9.0)
    quote(db, etf, 50, 0.0)
    make_score(db, lvmh, total=80, components=[
        {"key": "trend", "label": "Tendance", "points": 20, "max_points": 20, "message": "✅ Tendance", "group": "technical"},
        {"key": "rsi", "label": "RSI", "points": 6, "max_points": 10, "message": "⚠️ RSI", "group": "technical"},
        {"key": "valuation", "label": "Valorisation", "points": 12, "max_points": 15, "message": "✅ Valo", "group": "fundamental"},
        {"key": "macd", "label": "MACD", "points": 0, "max_points": 5, "message": "⚠️ MACD", "group": "technical"},
    ])
    make_score(db, total, total=70)
    make_score(db, small, total=95, liquid=False, eligible_for_top=False)
    make_score(db, etf, total=50, eligible_for_top=False)
    db.add(SecurityFundamentals(security_id=lvmh.id, pe=20.0, dividend_yield=0.02, market_cap=3e11, currency="EUR"))
    db.add(SecurityFundamentals(security_id=total.id, pe=8.0, market_cap=1e11, currency="EUR"))
    db.add(Favorite(user_id=user.id, security_id=total.id))
    db.flush()
    return lvmh, total, small, etf


def test_screener_stocks(client, db, user):
    seed(db, user)
    rows = client.get("/api/screener", params={"kind": "stock"}).json()
    assert [r["symbol"] for r in rows] == ["MC", "SMA", "TTE"]
    lvmh = rows[0]
    assert (lvmh["price"], lvmh["score"], lvmh["pe"], lvmh["dividend_yield"]) == (600, 80, 20.0, 0.02)
    assert lvmh["sparkline"] == [1.0, 2.0] and lvmh["is_favorite"] is False
    assert rows[2]["is_favorite"] is True


def test_screener_default_excludes_indices(client, db, user):
    seed(db, user)
    symbols = {r["symbol"] for r in client.get("/api/screener").json()}
    assert "CW8" in symbols and "^FCHI" not in symbols


def test_top_ranking_order_and_reasons(client, db, user):
    seed(db, user)
    top = client.get("/api/rankings/top").json()
    assert [t["symbol"] for t in top] == ["MC", "TTE"]
    assert top[0]["reasons"] == ["✅ Tendance", "✅ Valo", "⚠️ RSI"]


def test_top_ranking_limit_validation(client):
    assert client.get("/api/rankings/top", params={"limit": 0}).status_code == 422


def test_movers_only_liquid_eligible_stocks(client, db, user):
    seed(db, user)
    movers = client.get("/api/rankings/movers").json()
    assert [m["symbol"] for m in movers["gainers"]] == ["MC", "TTE"]
    assert [m["symbol"] for m in movers["losers"]] == ["TTE", "MC"]


def test_heatmap(client, db, user):
    seed(db, user)
    items = client.get("/api/market/heatmap").json()
    assert [i["symbol"] for i in items] == ["MC", "TTE"]
    assert items[0]["sector"] == "Autres"
    assert items[0]["market_cap_eur"] == 3e11


def test_status_indices_have_id(client, db, user):
    seed(db, user)
    index = client.get("/api/status").json()["indices"][0]
    assert isinstance(index["id"], int)


def test_screener_rows_list_eligible_envelopes(client, db):
    for security in (make_security(db, "ALCAR.PA", name="Carmat", pea_pme="eligible"),
                     make_security(db, "AAPL.PA", name="Apple", eligibility="non_eligible", country="US"),
                     make_security(db, "GFC.PA", name="Gecina", eligibility="a_verifier")):
        quote(db, security, 10, 0.0)
    rows = {r["name"]: r for r in client.get("/api/screener").json()}
    assert rows["Carmat"]["envelopes"] == ["pea", "pea_pme"]
    assert rows["Apple"]["envelopes"] == [] and rows["Gecina"]["envelopes"] == []
    assert "eligibility" not in rows["Carmat"]


def test_screener_hides_unpriced_and_filters_region(client, db):
    paris = make_security(db, "MC.PA", market="Euronext Paris")
    ny = make_security(db, "AAPL", market="Nasdaq", country="US")
    make_security(db, "RAW.DE", market="Xetra", country="AT")  # jamais coté sur Yahoo
    quote(db, paris, 600, 1.0)
    quote(db, ny, 200, 1.0)
    db.flush()
    assert {r["yahoo_ticker"] for r in client.get("/api/screener").json()} == {"MC.PA", "AAPL"}
    assert [r["yahoo_ticker"] for r in client.get("/api/screener", params={"region": "us"}).json()] == ["AAPL"]
    assert [r["yahoo_ticker"] for r in client.get("/api/screener", params={"region": "europe"}).json()] == ["MC.PA"]


def test_status_lists_each_place(client):
    markets = client.get("/api/status").json()["markets"]
    assert [(m["code"], m["label"]) for m in markets] == [("europe", "Europe"), ("us", "New York")]
    assert all(isinstance(m["open"], bool) for m in markets)
