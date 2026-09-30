from sqlalchemy import select

from app.models import EmailLog, Subscription
from app.services.billing.gateway import CheckoutInfo
from tests.factories import make_subscription, make_user


def test_sync_applies_the_paid_subscription(client, db, user, fake_billing):
    fake_billing.sessions["cs_1"] = CheckoutInfo("cs_1", str(user.id), "cus_1", "sub_1")
    fake_billing.put("sub_1", user_id=str(user.id))
    response = client.post("/api/billing/sync", json={"session_id": "cs_1"})
    assert response.status_code == 200 and response.json()["source"] == "subscription"
    assert db.scalar(select(EmailLog.kind)) == "premium_started"
    assert client.get("/api/me").json()["has_premium"] is True


def test_sync_refuses_a_session_of_another_user(client, db, fake_billing):
    other = make_user(db, "autre@example.com")
    fake_billing.sessions["cs_1"] = CheckoutInfo("cs_1", str(other.id), "cus_1", "sub_1")
    fake_billing.put("sub_1", user_id=str(other.id))
    response = client.post("/api/billing/sync", json={"session_id": "cs_1"})
    assert response.status_code == 404 and response.json()["detail"]["code"] == "not_found"
    assert db.scalar(select(Subscription)) is None


def test_sync_unknown_session_or_not_yet_paid(client, user, fake_billing):
    assert client.post("/api/billing/sync", json={"session_id": "cs_inconnue"}).status_code == 404
    fake_billing.sessions["cs_2"] = CheckoutInfo("cs_2", str(user.id), None, None)
    assert client.post("/api/billing/sync", json={"session_id": "cs_2"}).json()["source"] == "none"


def test_sync_when_stripe_is_down(client, user, fake_billing):
    fake_billing.down = True
    response = client.post("/api/billing/sync", json={"session_id": "cs_1"})
    assert response.status_code == 503 and response.json()["detail"]["code"] == "billing_unavailable"


def test_portal_opens_for_a_customer(client, db, user, fake_billing):
    make_subscription(db, user, status="canceled", customer_id="cus_7")
    db.refresh(user)
    assert client.post("/api/billing/portal").json() == {"url": "https://billing.stripe.test/cus_7"}
    assert fake_billing.portals == ["cus_7"]


def test_portal_without_customer_or_when_stripe_is_down(client, db, user, fake_billing):
    response = client.post("/api/billing/portal")
    assert response.status_code == 404 and response.json()["detail"]["code"] == "no_customer"
    make_subscription(db, user)
    db.refresh(user)
    fake_billing.down = True
    assert client.post("/api/billing/portal").status_code == 503
