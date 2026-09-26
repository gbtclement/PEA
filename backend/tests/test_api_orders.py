from datetime import date, timedelta

from app.models import Order
from tests.factories import make_security


def buy(security_id, qty=10, price=50.0, day="2026-03-02", **extra):
    return {"security_id": security_id, "trade_date": day, "side": "buy", "quantity": qty, "unit_price": price, **extra}


def test_create_order_computes_fee_from_grid(client, db):
    s = make_security(db, "MC.PA", name="LVMH")
    body = client.post("/api/orders", json=buy(s.id, qty=10, price=40)).json()
    assert body["fee"] == 1.92 and body["amount"] == 400.0 and body["name"] == "LVMH"
    body = client.post("/api/orders", json=buy(s.id, qty=10, price=60)).json()
    assert body["fee"] == 1.08  # 600 € → tranche 0,18 %


def test_manual_fee_is_kept(client, db):
    s = make_security(db, "MC.PA")
    assert client.post("/api/orders", json=buy(s.id, fee=0)).json()["fee"] == 0.0


def test_list_orders_most_recent_first(client, db):
    s = make_security(db, "MC.PA")
    client.post("/api/orders", json=buy(s.id, day="2026-01-05"))
    client.post("/api/orders", json=buy(s.id, day="2026-02-05"))
    assert [o["trade_date"] for o in client.get("/api/orders").json()] == ["2026-02-05", "2026-01-05"]


def test_create_sell_more_than_held_is_refused(client, db):
    s = make_security(db, "MC.PA", name="LVMH")
    client.post("/api/orders", json=buy(s.id, qty=3))
    response = client.post("/api/orders", json={**buy(s.id, qty=5, day="2026-04-01"), "side": "sell"})
    assert response.status_code == 422
    assert "3" in response.json()["detail"] and "LVMH" in response.json()["detail"]
    assert db.query(Order).count() == 1


def test_edit_buy_that_breaks_later_sell_is_refused(client, db):
    s = make_security(db, "MC.PA")
    first = client.post("/api/orders", json=buy(s.id, qty=10)).json()
    client.post("/api/orders", json={**buy(s.id, qty=8, day="2026-04-01"), "side": "sell"})
    assert client.put(f"/api/orders/{first['id']}", json=buy(s.id, qty=5)).status_code == 422
    assert client.put(f"/api/orders/{first['id']}", json=buy(s.id, qty=12, price=45)).json()["quantity"] == 12


def test_delete_buy_that_breaks_later_sell_is_refused(client, db):
    s = make_security(db, "MC.PA")
    first = client.post("/api/orders", json=buy(s.id, qty=10)).json()
    sale = client.post("/api/orders", json={**buy(s.id, qty=8, day="2026-04-01"), "side": "sell"}).json()
    assert client.delete(f"/api/orders/{first['id']}").status_code == 422
    assert client.delete(f"/api/orders/{sale['id']}").status_code == 204
    assert client.delete(f"/api/orders/{first['id']}").status_code == 204
    assert client.delete(f"/api/orders/{first['id']}").status_code == 404


def test_order_in_future_is_refused(client, db):
    s = make_security(db, "MC.PA")
    future = (date.today() + timedelta(days=3)).isoformat()
    assert client.post("/api/orders", json=buy(s.id, day=future)).status_code == 422


def test_order_validation(client, db):
    s = make_security(db, "MC.PA")
    assert client.post("/api/orders", json=buy(s.id, qty=0)).status_code == 422
    assert client.post("/api/orders", json=buy(s.id, price=-1)).status_code == 422
    assert client.post("/api/orders", json={**buy(s.id), "side": "short"}).status_code == 422
    assert client.post("/api/orders", json=buy(999999)).status_code == 404


def test_counter_counts_this_year(client, db):
    s = make_security(db, "MC.PA")
    today = date.today()
    client.post("/api/orders", json=buy(s.id, day=today.isoformat()))
    client.post("/api/orders", json=buy(s.id, day=date(today.year - 1, 6, 1).isoformat()))
    body = client.get("/api/orders/counter").json()
    assert (body["year"], body["count"], body["min_orders"], body["remaining"], body["penalty_fee"]) == (today.year, 1, 12, 11, 96.0)
