from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models import EmailLog, SecurityEvent, Subscription
from app.services.billing.state import apply_subscription, mail_context
from app.services.mail.render import render
from tests.factories import make_subscription, make_user
from tests.fake_billing import FakeBilling

NOW = datetime(2026, 10, 2, 10, 0, tzinfo=UTC)


def _kinds(db):
    return [m.kind for m in db.scalars(select(EmailLog).order_by(EmailLog.id))]


@pytest.fixture
def stripe():
    return FakeBilling()


def test_first_activation_sends_p1_and_logs(db, user, stripe):
    row = apply_subscription(db, user, stripe.put(user_id=str(user.id)), now=NOW)
    assert (row.status, row.interval, row.stripe_customer_id) == ("active", "month", "cus_1")
    assert user.has_premium
    assert _kinds(db) == ["premium_started"]
    assert db.scalar(select(SecurityEvent.kind).where(SecurityEvent.user_id == user.id)) == "subscription_started"


def test_replayed_state_sends_nothing_more(db, user, stripe):
    sub = stripe.put()
    apply_subscription(db, user, sub, now=NOW)
    apply_subscription(db, user, sub, now=NOW)
    assert _kinds(db) == ["premium_started"]


def test_cancel_scheduled_sends_p3_once_and_undo_sends_nothing(db, user, stripe):
    apply_subscription(db, user, stripe.put(), now=NOW)
    apply_subscription(db, user, stripe.update("sub_1", cancel_at_period_end=True), now=NOW)
    apply_subscription(db, user, stripe.update("sub_1", cancel_at_period_end=True), now=NOW)
    apply_subscription(db, user, stripe.update("sub_1", cancel_at_period_end=False), now=NOW)
    assert _kinds(db) == ["premium_started", "premium_canceling"]
    assert user.has_premium


def test_past_due_sends_p2_once_per_invoice_and_keeps_access(db, user, stripe):
    apply_subscription(db, user, stripe.put(), now=NOW)
    apply_subscription(db, user, stripe.update("sub_1", status="past_due", latest_invoice="in_2"), now=NOW)
    apply_subscription(db, user, stripe.update("sub_1", status="past_due", latest_invoice="in_2"), now=NOW)
    apply_subscription(db, user, stripe.update("sub_1", status="past_due", latest_invoice="in_3"), now=NOW)
    assert _kinds(db) == ["premium_started", "payment_failed", "payment_failed"]
    assert user.has_premium


def test_end_of_access_sends_p4_and_logs(db, user, stripe):
    apply_subscription(db, user, stripe.put(), now=NOW)
    apply_subscription(db, user, stripe.update("sub_1", status="canceled"), now=NOW)
    assert _kinds(db)[-1] == "premium_ended"
    assert not user.has_premium
    kinds = db.scalars(select(SecurityEvent.kind).where(SecurityEvent.user_id == user.id)).all()
    assert "subscription_ended" in kinds


def test_failed_new_attempt_does_not_override_an_active_subscription(db, user, stripe):
    apply_subscription(db, user, stripe.put("sub_1"), now=NOW)
    apply_subscription(db, user, stripe.put("sub_2", status="incomplete_expired"), now=NOW)  # Ruling 5
    assert db.get(Subscription, user.id).stripe_subscription_id == "sub_1"
    assert user.has_premium


def test_resubscribing_after_the_end_sends_p1_again(db, user, stripe):
    apply_subscription(db, user, stripe.put("sub_1"), now=NOW)
    apply_subscription(db, user, stripe.update("sub_1", status="canceled"), now=NOW)
    apply_subscription(db, user, stripe.put("sub_2"), now=NOW)
    assert _kinds(db) == ["premium_started", "premium_ended", "premium_started"]
    assert db.get(Subscription, user.id).stripe_subscription_id == "sub_2"


def test_offered_member_still_gets_subscription_mails(db, stripe):
    offered = make_user(db, "o@example.com", is_premium=True)
    apply_subscription(db, offered, stripe.put(), now=NOW)
    assert _kinds(db) == ["premium_started"]


@pytest.mark.parametrize("kind", ["premium_started", "payment_failed", "premium_canceling", "premium_ended",
                                  "renewal_reminder"])
def test_premium_mails_render_as_account_mails(db, kind):
    user = make_user(db, "r@example.com", first_name="Rémi")
    row = make_subscription(db, user, interval="year", cancel=True)
    mail = render(kind, mail_context(user, row, amount=4900, currency="eur"), base_url=get_settings().public_base_url)
    assert "Rémi" in mail.text and "Ne plus recevoir" not in mail.text
    assert "/reglages#abonnement" in mail.text or "/premium" in mail.text
    assert "01/11/2026" in mail.text or kind == "premium_ended"
