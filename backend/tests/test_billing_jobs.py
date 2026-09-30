from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.jobs.billing import process_cancellations, send_renewal_notices, sync_subscriptions
from app.models import EmailLog, StripeCancellation, Subscription
from tests.factories import make_subscription, make_user
from tests.fake_billing import FakeBilling

NIGHT = datetime(2026, 10, 2, 1, 30, tzinfo=UTC)


def _mails(db, kind=None):
    query = select(EmailLog.kind)
    return db.scalars(query.where(EmailLog.kind == kind) if kind else query).all()


def test_nightly_sync_applies_stripe_state_and_pushes_the_email(db, make_ctx):
    stripe = FakeBilling()
    user = make_user(db, "a@example.com")
    make_subscription(db, user, sub_id="sub_1", customer_id="cus_1")
    stripe.put("sub_1", customer_id="cus_1", status="canceled")
    assert sync_subscriptions(make_ctx(now=NIGHT, billing=stripe)) == 1
    assert db.get(Subscription, user.id).status == "canceled"
    assert _mails(db) == ["premium_ended"]
    assert stripe.emails == {"cus_1": "a@example.com"}


def test_nightly_sync_skips_long_ended_subscriptions_and_survives_errors(db, make_ctx):
    stripe = FakeBilling()
    old = make_user(db, "old@example.com")
    row = make_subscription(db, old, status="canceled", sub_id="sub_old", customer_id="cus_old")
    row.updated_at = NIGHT - timedelta(days=30)
    broken = make_user(db, "b@example.com")
    make_subscription(db, broken, sub_id="sub_missing", customer_id="cus_b")  # inconnu du faux Stripe : KeyError
    ok = make_user(db, "ok@example.com")
    make_subscription(db, ok, sub_id="sub_ok", customer_id="cus_ok")
    stripe.put("sub_ok", customer_id="cus_ok")
    db.flush()
    assert sync_subscriptions(make_ctx(now=NIGHT, billing=stripe)) == 1
    assert set(stripe.emails) == {"cus_ok"}


def test_nightly_sync_without_stripe_does_nothing(db, make_ctx):
    make_subscription(db, make_user(db, "a@example.com"))
    assert sync_subscriptions(make_ctx(now=NIGHT)) == 0


def test_renewal_notice_once_per_period_and_yearly_only(db, make_ctx):
    soon = NIGHT + timedelta(days=20)
    yearly = make_user(db, "y@example.com")
    make_subscription(db, yearly, interval="year", period_end=soon, sub_id="sub_y", customer_id="cus_y")
    make_subscription(db, make_user(db, "m@example.com"), interval="month", period_end=soon, sub_id="sub_m", customer_id="cus_m")
    make_subscription(db, make_user(db, "c@example.com"), interval="year", period_end=soon, cancel=True, sub_id="sub_c",
                      customer_id="cus_c")
    make_subscription(db, make_user(db, "l@example.com"), interval="year", period_end=NIGHT + timedelta(days=60),
                      sub_id="sub_l", customer_id="cus_l")
    ctx = make_ctx(now=NIGHT, billing=FakeBilling())
    assert send_renewal_notices(ctx) == 1
    assert send_renewal_notices(ctx) == 0
    mail = db.scalar(select(EmailLog).where(EmailLog.kind == "renewal_reminder"))
    assert mail.recipient == "y@example.com" and "49,00 €" in mail.text
    assert db.get(Subscription, yearly.id).renewal_notice_sent_for == soon


def test_cancellations_are_retried_until_stripe_answers(db, make_ctx):
    stripe = FakeBilling()
    db.add(StripeCancellation(subscription_id="sub_gone"))
    db.flush()
    stripe.down = True
    assert process_cancellations(make_ctx(now=NIGHT, billing=stripe)) == 0
    row = db.get(StripeCancellation, "sub_gone")
    assert row.attempts == 1 and row.last_error
    stripe.down = False
    assert process_cancellations(make_ctx(now=NIGHT, billing=stripe)) == 1
    assert stripe.canceled == ["sub_gone"] and db.get(StripeCancellation, "sub_gone") is None
