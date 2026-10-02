"""Petits défauts du Premium relevés à la revue finale (2026-10-01), corrigés le 2026-10-03."""
import json
from datetime import UTC, datetime, timedelta

import pytest
import stripe
from sqlalchemy import event, select

from app.jobs.billing import process_cancellations, sync_subscriptions
from app.models import BillingConsent, StripeCancellation, StripeEvent, Subscription, User
from app.services.billing.gateway import BillingRejected, InvalidSignature
from app.services.billing.state import apply_subscription
from app.services.billing.stripe_gateway import StripeGateway
from app.services.privacy.erasure import erase_account
from tests.factories import make_subscription, make_user
from tests.fake_billing import FakeBilling

NOW = datetime(2026, 10, 3, 10, 0, tzinfo=UTC)


def _webhook(test_client, subscription_id="sub_1", user_id=None):
    body = json.dumps({"id": "evt_1", "type": "customer.subscription.updated", "subscription_id": subscription_id,
                       "customer_id": "cus_1", "user_id": user_id})
    return test_client.post("/api/billing/webhook", content=body, headers={"Stripe-Signature": "bonne-signature"})


def test_sync_and_webhook_racing_on_the_first_subscription(db, user, monkeypatch):
    # /sync et le webhook créent la ligne en même temps : le second ne doit pas finir en erreur 500.
    make_subscription(db, user, status="incomplete", sub_id="sub_1", customer_id="cus_1")
    sub = FakeBilling().put("sub_1", user_id=str(user.id))
    real_get = db.get
    calls = []

    def stale_get(model, ident, **kwargs):
        if model is Subscription and not calls:
            calls.append(1)
            return None  # l'autre requête n'avait pas encore écrit sa ligne quand celle-ci l'a cherchée
        return real_get(model, ident, **kwargs)

    monkeypatch.setattr(db, "get", stale_get)
    row = apply_subscription(db, user, sub, now=NOW)
    assert (row.status, row.stripe_subscription_id) == ("active", "sub_1")


def test_webhook_with_a_permanent_stripe_refusal_is_acknowledged(anon_client, db, user, fake_billing):
    # Erreur 4xx définitive (abonnement inconnu, clé révoquée) : Stripe ne doit pas renvoyer l'événement pendant des jours.
    fake_billing.rejected.add("sub_1")
    response = _webhook(anon_client)
    assert response.status_code == 200
    assert db.get(StripeEvent, "evt_1") is not None


def test_stripe_client_errors_are_permanent_refusals():
    gateway = StripeGateway(secret_key="sk_test_x", webhook_secret="w", price_monthly="m", price_yearly="y")

    def missing(*args, **kwargs):
        raise stripe.InvalidRequestError("No such subscription", param="id", code="resource_missing")

    with pytest.raises(BillingRejected):
        gateway._call(missing)


def test_non_utf8_webhook_body_is_a_bad_signature():
    gateway = StripeGateway(secret_key="sk_test_x", webhook_secret="whsec_test", price_monthly="m", price_yearly="y")
    with pytest.raises(InvalidSignature):
        gateway.parse_event(b"\xff\xfe pas du texte", "t=1,v1=abc")


def test_sync_is_rate_limited(client, user, fake_billing):
    codes = [client.post("/api/billing/sync", json={"session_id": "cs_inconnue"}).status_code for _ in range(31)]
    assert codes[:30] == [404] * 30 and codes[30] == 429


def test_config_status_counts_pending_cancellations(admin_client, db):
    db.add_all([StripeCancellation(subscription_id="sub_a"), StripeCancellation(subscription_id="sub_b")])
    db.flush()
    assert admin_client.get("/api/admin/config-status").json()["stripe_pending_cancellations"] == 2


@pytest.mark.parametrize("status", ["unpaid", "paused"])
def test_suspended_subscription_cannot_start_a_second_checkout(client, db, user, fake_billing, status):
    make_subscription(db, user, status=status)
    db.refresh(user)
    response = client.post("/api/billing/checkout", json={"interval": "month", "accept_cgv": True, "waive_withdrawal": True})
    assert response.status_code == 409 and response.json()["detail"]["code"] == "subscription_suspended"
    assert fake_billing.checkouts == []


def test_erasing_an_account_expires_its_open_checkout_pages(db, make_ctx):
    user = make_user(db, "c@example.com")
    db.add_all([
        BillingConsent(user_id=user.id, cgv_version="2026-10-05", withdrawal_waiver=True, interval="month",
                       accepted_at=NOW - timedelta(hours=1), checkout_session_id="cs_open"),
        BillingConsent(user_id=user.id, cgv_version="2026-10-05", withdrawal_waiver=True, interval="month",
                       accepted_at=NOW - timedelta(days=3), checkout_session_id="cs_old"),  # déjà expirée chez Stripe
    ])
    db.flush()
    erase_account(db, user, now=NOW)
    assert db.get(StripeCancellation, "cs_open") is not None and db.get(StripeCancellation, "cs_old") is None
    billing = FakeBilling()
    process_cancellations(make_ctx(billing=billing))
    assert billing.expired == ["cs_open"] and billing.canceled == []


def test_nightly_email_failure_keeps_the_state_refresh(db, make_ctx):
    user = make_user(db, "d@example.com")
    make_subscription(db, user, status="active", sub_id="sub_d", customer_id="cus_d")
    billing = FakeBilling()
    billing.put("sub_d", customer_id="cus_d", user_id=str(user.id), status="past_due", latest_invoice=None)
    billing.email_fails = True
    sync_subscriptions(make_ctx(billing=billing, now=NOW))
    db.expire_all()
    assert db.get(Subscription, user.id).status == "past_due"


def test_loading_a_user_also_loads_the_subscription(db, user):
    make_subscription(db, user)
    db.flush()
    db.expire_all()
    statements = []

    def count(conn, cursor, statement, *args):
        statements.append(statement)

    event.listen(db.bind, "before_cursor_execute", count)
    try:
        loaded = db.scalar(select(User).where(User.id == user.id))
        assert loaded.subscription is not None
    finally:
        event.remove(db.bind, "before_cursor_execute", count)
    # has_premium est lu à chaque requête : l'abonnement vient avec le compte, jamais par une requête à part.
    assert statements and all("JOIN subscriptions" in s for s in statements)
    assert not any(s.lstrip().startswith("SELECT subscriptions") for s in statements)
