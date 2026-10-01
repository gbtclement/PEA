import json
import uuid

from sqlalchemy import select

from app.api.deps import get_billing_gateway
from app.models import EmailLog, StripeEvent, Subscription
from tests.factories import make_subscription


def _send(test_client, event_id="evt_1", type_="checkout.session.completed", subscription_id="sub_1",
          customer_id="cus_1", user_id=None, signature="bonne-signature"):
    body = json.dumps({"id": event_id, "type": type_, "subscription_id": subscription_id, "customer_id": customer_id,
                       "user_id": user_id})
    headers = {"Stripe-Signature": signature} if signature else {}
    return test_client.post("/api/billing/webhook", content=body, headers=headers)


def _mails(db):
    return db.scalars(select(EmailLog.kind)).all()


def test_bad_or_missing_signature_is_rejected(anon_client, db, user, fake_billing):
    fake_billing.put("sub_1", user_id=str(user.id))
    for signature in ("fausse", None):
        response = _send(anon_client, user_id=str(user.id), signature=signature)
        assert response.status_code == 400 and response.json()["detail"]["code"] == "bad_signature"
    assert db.scalar(select(Subscription)) is None and db.scalar(select(StripeEvent)) is None


def test_checkout_completed_activates_premium(anon_client, db, user, fake_billing):
    fake_billing.put("sub_1", user_id=str(user.id))
    assert _send(anon_client, user_id=str(user.id)).json() == {"received": True}
    db.refresh(user)
    assert user.has_premium and _mails(db) == ["premium_started"]


def test_same_event_twice_is_applied_once(anon_client, db, user, fake_billing):
    fake_billing.put("sub_1", user_id=str(user.id))
    _send(anon_client, user_id=str(user.id))
    _send(anon_client, user_id=str(user.id))
    assert _mails(db) == ["premium_started"]
    assert len(db.scalars(select(StripeEvent)).all()) == 1


def test_state_is_read_back_from_stripe(anon_client, db, user, fake_billing):
    fake_billing.put("sub_1", user_id=str(user.id), status="canceled")  # « créé » arrive après la suppression
    _send(anon_client, type_="customer.subscription.created", user_id=str(user.id))
    db.refresh(user)
    assert not user.has_premium and _mails(db) == []


def test_user_found_by_customer_id(anon_client, db, user, fake_billing):
    make_subscription(db, user, sub_id="sub_1", customer_id="cus_1")
    fake_billing.put("sub_1", customer_id="cus_1", status="past_due", latest_invoice="in_2")
    _send(anon_client, type_="invoice.payment_failed")
    assert _mails(db) == ["payment_failed"]


def test_unknown_user_gets_the_subscription_canceled(anon_client, db, fake_billing):
    fake_billing.put("sub_9", customer_id="cus_9")
    response = _send(anon_client, subscription_id="sub_9", customer_id="cus_9", user_id=str(uuid.uuid4()))
    assert response.status_code == 200 and fake_billing.canceled == ["sub_9"]


def test_other_event_types_are_acknowledged_only(anon_client, db, fake_billing):
    assert _send(anon_client, type_="customer.created", subscription_id=None).status_code == 200
    assert db.scalar(select(StripeEvent.type)) == "customer.created" and db.scalar(select(Subscription)) is None


def test_stripe_down_returns_500_and_event_is_not_marked(anon_client, db, user, fake_billing):
    fake_billing.put("sub_1", user_id=str(user.id))
    fake_billing.down = True
    response = _send(anon_client, user_id=str(user.id))
    assert response.status_code == 500 and db.scalar(select(StripeEvent)) is None


def test_webhook_without_stripe(anon_client):
    anon_client.app.dependency_overrides[get_billing_gateway] = lambda: None
    assert _send(anon_client).status_code == 503
