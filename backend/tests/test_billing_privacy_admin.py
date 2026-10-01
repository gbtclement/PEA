from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.models import BillingConsent, StripeCancellation, StripeEvent, Subscription
from app.services.privacy.erasure import erase_account
from app.services.privacy.export import build_export
from app.services.privacy.retention import run_retention
from tests.factories import make_subscription, make_user

NOW = datetime(2026, 10, 2, 10, 0, tzinfo=UTC)


def test_erasing_a_subscriber_queues_the_cancellation(db):
    user = make_user(db, "a@example.com")
    make_subscription(db, user, sub_id="sub_live")
    db.add(BillingConsent(user_id=user.id, cgv_version="2026-10-05", withdrawal_waiver=True, interval="month", accepted_at=NOW))
    db.flush()
    erase_account(db, user, now=NOW)
    assert db.get(StripeCancellation, "sub_live") is not None
    assert db.scalar(select(Subscription)) is None and db.scalar(select(BillingConsent)) is None


def test_erasing_an_ended_subscription_queues_nothing(db):
    user = make_user(db, "b@example.com")
    make_subscription(db, user, status="canceled", sub_id="sub_done")
    erase_account(db, user, now=NOW)
    assert db.scalar(select(StripeCancellation)) is None


def test_export_contains_the_subscription_without_stripe_ids(db):
    user = make_user(db, "c@example.com")
    make_subscription(db, user, interval="year", cancel=True, sub_id="sub_secret", customer_id="cus_secret")
    db.add(BillingConsent(user_id=user.id, cgv_version="2026-10-05", withdrawal_waiver=True, interval="year", accepted_at=NOW))
    db.flush()
    db.refresh(user)
    data = build_export(db, user, NOW)
    assert data["abonnement"] == {"formule": "year", "etat": "active", "fin_de_periode": "2026-11-01T00:00:00+00:00",
                                  "resiliation_demandee": True}
    assert data["accords_de_vente"][0]["version_cgv"] == "2026-10-05"
    assert "sub_secret" not in str(data) and "cus_secret" not in str(data)


def test_stripe_events_are_kept_30_days(db):
    db.add_all([StripeEvent(id="evt_old", type="x", received_at=NOW - timedelta(days=31)),
                StripeEvent(id="evt_new", type="x", received_at=NOW - timedelta(days=1))])
    db.flush()
    assert run_retention(db, NOW)["stripe_events"] == 1
    assert db.scalars(select(StripeEvent.id)).all() == ["evt_new"]


def test_admin_list_shows_the_premium_source(admin_client, db):
    subscriber = make_user(db, "s@example.com")
    make_subscription(db, subscriber, interval="year")
    make_user(db, "o@example.com", is_premium=True)
    items = {u["email"]: u for u in admin_client.get("/api/admin/users").json()["items"]}
    assert (items["s@example.com"]["premium_source"], items["s@example.com"]["subscription_interval"]) == ("subscription", "year")
    assert items["o@example.com"]["premium_source"] == "offered"
    assert items["admin@example.com"]["premium_source"] == "admin"


def test_config_status_shows_stripe_without_values(admin_client, db):
    db.add(StripeEvent(id="evt_1", type="invoice.paid", received_at=NOW))
    db.flush()
    body = admin_client.get("/api/admin/config-status").json()
    assert (body["stripe"], body["stripe_mode"]) == (True, "test")
    assert body["stripe_last_webhook_at"].startswith("2026-10-02")
    for secret in ("sk_", "whsec_", "price_"):
        assert secret not in str(body)
    assert get_settings().stripe_secret_key == "" or get_settings().stripe_secret_key not in str(body)
