import hashlib
import hmac
import json
import time
from datetime import UTC, datetime

import pytest

from app.services.billing.gateway import InvalidSignature, event_from_dict, subscription_from_dict
from app.services.billing.stripe_gateway import StripeGateway

PERIOD_END = 1793491200  # 2026-11-01 00:00 UTC


def _sub(**over):
    data = {"id": "sub_1", "customer": "cus_1", "status": "active", "metadata": {"user_id": "u-1"},
            "cancel_at_period_end": False, "cancel_at": None, "latest_invoice": "in_1",
            "items": {"data": [{"current_period_end": PERIOD_END,
                                "price": {"unit_amount": 499, "currency": "eur", "recurring": {"interval": "month"}}}]}}
    data.update(over)
    return data


def test_subscription_reads_the_period_on_the_item():
    sub = subscription_from_dict(_sub())
    assert (sub.id, sub.customer_id, sub.user_id, sub.status, sub.interval) == ("sub_1", "cus_1", "u-1", "active", "month")
    assert sub.current_period_end == datetime(2026, 11, 1, tzinfo=UTC)
    assert (sub.cancel_at_period_end, sub.ends_at, sub.latest_invoice) == (False, None, "in_1")
    assert (sub.price_amount, sub.currency) == (499, "eur")


def test_subscription_legacy_period_and_cancel_at():
    data = _sub(current_period_end=PERIOD_END, cancel_at=PERIOD_END - 86400)
    data["items"]["data"][0].pop("current_period_end")
    sub = subscription_from_dict(data)
    assert sub.current_period_end == datetime(2026, 11, 1, tzinfo=UTC)
    assert sub.cancel_at_period_end is True  # Ruling 3
    assert sub.ends_at == datetime(2026, 10, 31, tzinfo=UTC)


def test_expanded_customer_and_invoice_objects():
    sub = subscription_from_dict(_sub(customer={"id": "cus_9"}, latest_invoice={"id": "in_9"}))
    assert (sub.customer_id, sub.latest_invoice) == ("cus_9", "in_9")


@pytest.mark.parametrize("obj, expected", [
    ({"object": "checkout.session", "id": "cs_1", "subscription": "sub_1", "customer": "cus_1",
      "client_reference_id": "u-1", "metadata": {}}, ("sub_1", "cus_1", "u-1")),
    ({"object": "subscription", "id": "sub_2", "customer": "cus_2", "metadata": {"user_id": "u-2"}}, ("sub_2", "cus_2", "u-2")),
    ({"object": "invoice", "id": "in_3", "customer": "cus_3",
      "parent": {"subscription_details": {"subscription": "sub_3", "metadata": {"user_id": "u-3"}}}}, ("sub_3", "cus_3", "u-3")),
    ({"object": "invoice", "id": "in_4", "customer": "cus_4", "subscription": "sub_4"}, ("sub_4", "cus_4", None)),
])
def test_event_targets(obj, expected):
    event = event_from_dict({"id": "evt_1", "type": "x", "data": {"object": obj}})
    assert (event.subscription_id, event.customer_id, event.user_id) == expected


def _signed(payload: bytes, secret: str, at: int | None = None) -> str:
    at = at or int(time.time())
    sig = hmac.new(secret.encode(), f"{at}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={at},v1={sig}"


def test_parse_event_checks_the_signature():
    gateway = StripeGateway(secret_key="sk_test_x", webhook_secret="whsec_test", price_monthly="p_m", price_yearly="p_y")
    payload = json.dumps({"id": "evt_1", "type": "invoice.paid", "data": {"object": {"object": "invoice", "customer": "cus_1",
                                                                                     "subscription": "sub_1"}}}).encode()
    assert gateway.parse_event(payload, _signed(payload, "whsec_test")).id == "evt_1"
    for bad in (None, "", _signed(payload, "whsec_other"), _signed(payload, "whsec_test", at=int(time.time()) - 600)):
        with pytest.raises(InvalidSignature):
            gateway.parse_event(payload, bad)


def test_mode_comes_from_the_key_prefix():
    assert StripeGateway(secret_key="sk_live_x", webhook_secret="w", price_monthly="m", price_yearly="y").mode == "live"
    assert StripeGateway(secret_key="sk_test_x", webhook_secret="w", price_monthly="m", price_yearly="y").mode == "test"
