from datetime import UTC, datetime

from app.models import SecurityQuote
from app.repositories.data_status import record_success
from tests.factories import make_security

AS_OF = datetime(2026, 9, 25, 15, 35, tzinfo=UTC)


def seed(db):
    oreal = make_security(db, "OR.PA", name="L'Oréal", isin="FR0000120321")
    lvmh = make_security(db, "MC.PA", name="LVMH", isin="FR0000121014")
    cw8 = make_security(db, "CW8.PA", name="Amundi MSCI World", kind="etf")
    cac = make_security(db, "^FCHI", name="CAC 40", kind="index", eligibility="non_eligible", country=None)
    mmm = make_security(db, "MMM.PA", name="3M", eligibility="non_eligible", country="US")
    make_security(db, "OLD.PA", name="Ancienne", active=False)
    db.add(SecurityQuote(security_id=lvmh.id, price=612.4, previous_close=600, change_pct=2.07, volume=1, as_of=AS_OF))
    for other in (oreal, cw8, cac, mmm):  # les titres sans aucun cours ne sont pas listés
        db.add(SecurityQuote(security_id=other.id, price=10.0, previous_close=10.0, change_pct=0.0, volume=1, as_of=AS_OF))
    db.flush()
    return oreal, lvmh


def test_list_excludes_indices_and_inactive(client, db):
    seed(db)
    body = client.get("/api/securities").json()
    assert [i["yahoo_ticker"] for i in body["items"]] == ["MMM.PA", "CW8.PA", "OR.PA", "MC.PA"]
    assert body["total"] == 4


def test_list_includes_quote(client, db):
    seed(db)
    item = next(i for i in client.get("/api/securities").json()["items"] if i["yahoo_ticker"] == "MC.PA")
    assert item["price"] == 612.4
    assert item["change_pct"] == 2.07
    assert item["as_of"].startswith("2026-09-25")
    oreal = next(i for i in client.get("/api/securities").json()["items"] if i["yahoo_ticker"] == "OR.PA")
    assert oreal["price"] == 10.0


def test_search_case_insensitive_by_name_symbol_isin(client, db):
    seed(db)
    assert [i["symbol"] for i in client.get("/api/securities", params={"q": "lvmh"}).json()["items"]] == ["MC"]
    assert [i["symbol"] for i in client.get("/api/securities", params={"q": "mc"}).json()["items"]] == ["MC"]
    assert [i["symbol"] for i in client.get("/api/securities", params={"q": "FR0000120321"}).json()["items"]] == ["OR"]


def test_search_apostrophe(client, db):
    seed(db)
    response = client.get("/api/securities", params={"q": "L'Or"})
    assert response.status_code == 200
    assert [i["symbol"] for i in response.json()["items"]] == ["OR"]


def test_search_wildcards_are_literal(client, db):
    seed(db)
    for q in ["%", "_", "\\"]:
        response = client.get("/api/securities", params={"q": q})
        assert response.status_code == 200
        assert response.json()["total"] == 0


def test_filters_and_pagination(client, db):
    seed(db)
    assert client.get("/api/securities", params={"kind": "etf"}).json()["total"] == 1
    assert client.get("/api/securities", params={"kind": "index"}).json()["items"][0]["yahoo_ticker"] == "^FCHI"
    assert client.get("/api/securities", params={"envelope": "pea"}).json()["total"] == 3  # L'Oréal, LVMH, l'ETF
    assert client.get("/api/securities", params={"envelope": "livret"}).status_code == 422
    page = client.get("/api/securities", params={"limit": 2, "offset": 2}).json()
    assert page["total"] == 4 and len(page["items"]) == 2


def test_invalid_params_are_rejected(client):
    assert client.get("/api/securities", params={"limit": 0}).status_code == 422
    assert client.get("/api/securities", params={"kind": "crypto"}).status_code == 422


def test_status(client, db):
    seed(db)
    record_success(db, "quotes_t1", 3, AS_OF)
    db.flush()
    body = client.get("/api/status").json()
    assert isinstance(body["market_open"], bool)
    assert body["jobs"][0]["job"] == "quotes_t1"
    assert body["jobs"][0]["last_count"] == 3
    assert [i["yahoo_ticker"] for i in body["indices"]] == ["^FCHI"]


def test_search_hides_unpriced(client, db):
    make_security(db, "RAW.DE", market="Xetra", name="Raiffeisen")
    assert client.get("/api/securities", params={"q": "Raiff"}).json()["total"] == 0


def test_search_gives_the_quote_currency(client, db):
    ny = make_security(db, "AAPL", market="Nasdaq", name="Apple", country="US")
    db.add(SecurityQuote(security_id=ny.id, price=250.0, previous_close=248, change_pct=0.8, volume=1, as_of=AS_OF))
    db.flush()
    [item] = client.get("/api/securities", params={"q": "Apple"}).json()["items"]
    assert item["currency"] == "USD"
