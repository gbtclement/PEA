from datetime import date

import pytest

from app.models import Order
from tests.auth_helpers import sign_in
from tests.factories import make_security, make_user

PRIVATE = [
    ("GET", "/api/orders"), ("GET", "/api/orders/counter"), ("POST", "/api/orders"),
    ("GET", "/api/portfolio"), ("GET", "/api/portfolio/history"),
    ("PUT", "/api/favorites/1"), ("DELETE", "/api/favorites/1"),
    ("GET", "/api/settings"), ("PUT", "/api/settings"),
    ("GET", "/api/assistant/status"), ("GET", "/api/assistant/conversations"),
    ("GET", "/api/forecasts"), ("GET", "/api/forecasts/signals"), ("GET", "/api/forecasts/track-record"),
    ("GET", "/api/securities/1/forecast"),
    ("PATCH", "/api/securities/1/eligibility"),
    ("GET", "/api/billing/subscription"), ("POST", "/api/billing/checkout"),
]
PUBLIC = ["/api/screener?kind=stock", "/api/rankings/top", "/api/rankings/movers", "/api/market/heatmap",
          "/api/securities", "/api/status", "/api/fees/estimate?amount=1000", "/api/health",
          "/api/billing/plans"]


@pytest.mark.parametrize(("method", "path"), PRIVATE)
def test_private_routes_need_a_session(anon_client, method, path):
    response = anon_client.request(method, path, json={})
    assert response.status_code == 401, path


@pytest.mark.parametrize("path", PUBLIC)
def test_public_routes_work_without_account(anon_client, path):
    assert anon_client.get(path).status_code == 200, path


def test_anonymous_security_page_has_no_favourite(anon_client, db):
    security = make_security(db, "MC.PA")
    body = anon_client.get(f"/api/securities/{security.id}").json()
    assert body["is_favorite"] is False
    assert anon_client.get(f"/api/securities/{security.id}/simulate?amount=1000&period=1M").status_code == 200


def test_unsafe_request_without_csrf_header_is_refused(client):
    del client.headers["X-CSRF-Token"]
    response = client.put("/api/favorites/1")
    assert response.status_code == 403 and response.json()["detail"]["code"] == "csrf"


def test_eligibility_override_is_admin_only(client, anon_client, db):
    security = make_security(db, "MC.PA")
    assert client.patch(f"/api/securities/{security.id}/eligibility", json={"override": "non_eligible"}).status_code == 403
    sign_in(anon_client, db, make_user(db, "admin@example.com", role="admin"))
    assert anon_client.patch(f"/api/securities/{security.id}/eligibility", json={"override": "non_eligible"}).status_code == 200


def test_users_never_see_each_other_orders_or_favourites(client, anon_client, db, user):
    security = make_security(db, "MC.PA")
    other = make_user(db, "autre@example.com")
    db.add(Order(user_id=other.id, security_id=security.id, trade_date=date(2026, 9, 1), side="buy",
                 quantity=1, unit_price=10.0, fee=1.0))
    db.flush()
    sign_in(anon_client, db, other)
    assert anon_client.put(f"/api/favorites/{security.id}").status_code == 204
    assert client.get("/api/orders").json() == []
    assert client.get(f"/api/securities/{security.id}").json()["is_favorite"] is False
    order_id = anon_client.get("/api/orders").json()[0]["id"]
    assert client.delete(f"/api/orders/{order_id}").status_code == 404
    assert str(other.id) not in client.get("/api/orders").text
