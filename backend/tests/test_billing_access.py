from datetime import UTC, datetime

import pytest

from app.core.config import Settings
from app.services.billing.access import premium_source
from tests.factories import make_subscription, make_user


def test_admin_and_offered_premium(db):
    assert premium_source(make_user(db, "a@example.com", role="admin")) == "admin"
    assert premium_source(make_user(db, "o@example.com", is_premium=True)) == "offered"
    assert premium_source(make_user(db, "f@example.com")) == "none"


@pytest.mark.parametrize("status, source", [
    ("active", "subscription"), ("past_due", "subscription"), ("trialing", "subscription"),
    ("canceled", "none"), ("unpaid", "none"), ("incomplete", "none"), ("incomplete_expired", "none"), ("paused", "none"),
])
def test_each_stripe_status(db, status, source):
    user = make_user(db, "s@example.com")
    make_subscription(db, user, status=status)
    db.refresh(user)
    assert premium_source(user) == source
    assert user.has_premium is (source != "none")


def test_offered_wins_over_a_canceled_subscription(db):
    user = make_user(db, "o@example.com", is_premium=True)
    make_subscription(db, user, status="canceled")
    db.refresh(user)
    assert premium_source(user) == "offered"


def test_me_exposes_the_source(client, db, user):
    make_subscription(db, user)
    db.refresh(user)
    body = client.get("/api/me").json()
    assert (body["has_premium"], body["premium_source"]) == (True, "subscription")


def test_stripe_configured_needs_the_four_variables():
    full = dict(stripe_secret_key="sk_test_x", stripe_webhook_secret="whsec_x", stripe_price_monthly="price_m",
                stripe_price_yearly="price_y")
    assert Settings(**full).stripe_configured
    assert not Settings(**{**full, "stripe_price_yearly": ""}).stripe_configured


def test_user_deletion_cascades(db):
    from app.models import Subscription

    user = make_user(db, "c@example.com")
    make_subscription(db, user, period_end=datetime(2026, 11, 1, tzinfo=UTC))
    db.delete(user)
    db.flush()
    assert db.query(Subscription).count() == 0
