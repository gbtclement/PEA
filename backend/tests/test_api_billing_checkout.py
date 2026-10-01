from sqlalchemy import select

from app.api.deps import get_billing_gateway
from app.models import BillingConsent, SecurityEvent
from tests.factories import make_subscription

BOTH = {"interval": "year", "accept_cgv": True, "waive_withdrawal": True}


def _no_stripe(test_client):
    test_client.app.dependency_overrides[get_billing_gateway] = lambda: None


def test_plans_are_public_with_the_yearly_saving(anon_client):
    body = anon_client.get("/api/billing/plans").json()
    assert body["configured"] is True
    assert [(p["interval"], p["amount"], p["currency"]) for p in body["plans"]] == [("month", 499, "eur"), ("year", 4900, "eur")]
    assert body["yearly_saving_pct"] == 18  # 49 € au lieu de 12 × 4,99 €


def test_plans_without_stripe_or_when_stripe_is_down(anon_client, fake_billing):
    fake_billing.down = True
    assert anon_client.get("/api/billing/plans").json() == {"configured": True, "plans": [], "yearly_saving_pct": None}
    _no_stripe(anon_client)
    assert anon_client.get("/api/billing/plans").json() == {"configured": False, "plans": [], "yearly_saving_pct": None}


def test_checkout_records_consent_and_returns_the_stripe_url(client, db, user, fake_billing):
    response = client.post("/api/billing/checkout", json=BOTH)
    assert response.status_code == 200
    assert response.json() == {"url": "https://checkout.stripe.test/cs_1"}
    call = fake_billing.checkouts[0]
    assert (call["interval"], call["user_id"], call["email"], call["customer_id"]) == ("year", str(user.id), user.email, None)
    assert call["success_url"].endswith("/premium/merci?session_id={CHECKOUT_SESSION_ID}")
    assert call["cancel_url"].endswith("/premium")
    consent = db.scalar(select(BillingConsent).where(BillingConsent.user_id == user.id))
    assert (consent.withdrawal_waiver, consent.interval, consent.checkout_session_id) == (True, "year", "cs_1")
    assert db.scalar(select(SecurityEvent.kind).where(SecurityEvent.user_id == user.id)) == "billing_consent"


def test_checkout_reuses_the_stripe_customer(client, db, user, fake_billing):
    make_subscription(db, user, status="canceled", customer_id="cus_old")
    db.refresh(user)
    assert client.post("/api/billing/checkout", json=BOTH).status_code == 200
    assert fake_billing.checkouts[0]["customer_id"] == "cus_old"


def test_both_boxes_are_required(client, db, fake_billing):
    for payload in ({**BOTH, "accept_cgv": False}, {**BOTH, "waive_withdrawal": False}):
        response = client.post("/api/billing/checkout", json=payload)
        assert response.status_code == 422 and response.json()["detail"]["code"] == "consent_required"
    assert fake_billing.checkouts == [] and db.scalar(select(BillingConsent)) is None


def test_already_subscribed_or_offered_cannot_checkout(client, db, user):
    make_subscription(db, user)
    db.refresh(user)
    assert client.post("/api/billing/checkout", json=BOTH).json()["detail"]["code"] == "already_premium"
    user.subscription.status = "canceled"
    user.is_premium = True
    db.flush()
    response = client.post("/api/billing/checkout", json=BOTH)
    assert response.status_code == 409 and response.json()["detail"]["code"] == "premium_offered"


def test_checkout_is_rate_limited(client):
    for _ in range(10):
        assert client.post("/api/billing/checkout", json=BOTH).status_code == 200
    response = client.post("/api/billing/checkout", json=BOTH)
    assert response.status_code == 429 and response.json()["detail"]["code"] == "too_many_attempts"


def test_checkout_when_stripe_is_down_keeps_the_consent(client, db, fake_billing):
    fake_billing.down = True
    response = client.post("/api/billing/checkout", json=BOTH)
    assert response.status_code == 503 and response.json()["detail"]["code"] == "billing_unavailable"
    assert db.scalar(select(BillingConsent)).checkout_session_id is None


def test_checkout_without_stripe(client):
    _no_stripe(client)
    response = client.post("/api/billing/checkout", json=BOTH)
    assert response.status_code == 503 and response.json()["detail"]["code"] == "billing_not_configured"


def test_subscription_summary(client, db, user):
    assert client.get("/api/billing/subscription").json() == {
        "source": "none", "status": None, "interval": None, "current_period_end": None, "cancel_at_period_end": False,
        "has_customer": False}
    make_subscription(db, user, interval="year", cancel=True)
    db.refresh(user)
    body = client.get("/api/billing/subscription").json()
    assert (body["source"], body["status"], body["interval"], body["cancel_at_period_end"], body["has_customer"]) == (
        "subscription", "active", "year", True, True)
    assert body["current_period_end"].startswith("2026-11-01")
