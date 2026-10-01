import uuid
from datetime import UTC, datetime

from app.models import PriceAlert
from tests.factories import make_quote, make_security, make_user

DEFAULTS = {"price_move": True, "price_alert": True, "daily_recap": False, "weekly_recap": False,
            "order_reminder": True, "score_change": False, "move_threshold_pct": 5.0}


def test_prefs_round_trip(client):
    assert client.get("/api/me/notifications").json() == DEFAULTS
    body = {**DEFAULTS, "daily_recap": True, "move_threshold_pct": 3}
    assert client.put("/api/me/notifications", json=body).status_code == 200
    assert client.get("/api/me/notifications").json() == {**body, "move_threshold_pct": 3.0}


def test_threshold_between_1_and_50(client):
    assert client.put("/api/me/notifications", json={**DEFAULTS, "move_threshold_pct": 0.5}).status_code == 422
    assert client.put("/api/me/notifications", json={**DEFAULTS, "move_threshold_pct": 51}).status_code == 422


def test_create_list_rearm_delete_alert(client, db):
    security = make_security(db, "MC.PA", name="LVMH")
    make_quote(db, security, 100.0)
    created = client.post("/api/me/price-alerts", json={"security_id": security.id, "direction": "above", "price": 110})
    assert created.status_code == 201
    alert = created.json()
    assert (alert["name"], alert["currency"], alert["price"], alert["current_price"], alert["active"]) == (
        "LVMH", "EUR", 110.0, 100.0, True)
    reached = client.post("/api/me/price-alerts", json={"security_id": security.id, "direction": "above", "price": 90})
    assert reached.status_code == 400 and reached.json()["detail"]["code"] == "already_reached"

    row = db.get(PriceAlert, uuid.UUID(alert["id"]))
    row.active, row.triggered_at = False, datetime.now(UTC)
    rearmed = client.patch(f"/api/me/price-alerts/{alert['id']}", json={"active": True, "price": 120})
    assert rearmed.status_code == 200
    assert (rearmed.json()["active"], rearmed.json()["triggered_at"], rearmed.json()["price"]) == (True, None, 120.0)

    assert client.delete(f"/api/me/price-alerts/{alert['id']}").status_code == 204
    assert client.get("/api/me/price-alerts").json() == []


def test_fifty_active_alerts_at_most(client, db, user):
    security = make_security(db, "MC.PA")
    make_quote(db, security, 100.0)
    db.add_all(PriceAlert(user_id=user.id, security_id=security.id, direction="above", price=200 + i) for i in range(50))
    db.flush()
    response = client.post("/api/me/price-alerts", json={"security_id": security.id, "direction": "below", "price": 50})
    assert response.status_code == 400 and response.json()["detail"]["code"] == "alert_limit"


def test_alerts_of_another_user_are_404(client, db):
    security = make_security(db, "MC.PA")
    other = make_user(db, "autre@example.com")
    alert = PriceAlert(user_id=other.id, security_id=security.id, direction="above", price=150)
    db.add(alert)
    db.flush()
    assert client.get("/api/me/price-alerts").json() == []
    assert client.patch(f"/api/me/price-alerts/{alert.id}", json={"active": False}).status_code == 404
    assert client.delete(f"/api/me/price-alerts/{alert.id}").status_code == 404


def test_unknown_security_is_404(client):
    response = client.post("/api/me/price-alerts", json={"security_id": 999999, "direction": "above", "price": 10})
    assert response.status_code == 404


def test_visitors_get_401(anon_client):
    assert anon_client.get("/api/me/notifications").status_code == 401
    assert anon_client.get("/api/me/price-alerts").status_code == 401
