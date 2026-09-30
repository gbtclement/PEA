"""Implémentation de BillingGateway avec la bibliothèque officielle `stripe` (StripeClient, espace v1)."""
import json
from typing import Literal

import stripe

from app.services.billing.gateway import (
    BillingUnavailable, CheckoutInfo, InvalidSignature, Plan, StripeEventIn, StripeSubscription, event_from_dict,
    subscription_from_dict,
)

TOLERANCE_SECONDS = 300


class StripeGateway:
    def __init__(self, *, secret_key: str, webhook_secret: str, price_monthly: str, price_yearly: str):
        self._client = stripe.StripeClient(secret_key, max_network_retries=2)
        self._webhook_secret = webhook_secret
        self._prices = {"month": price_monthly, "year": price_yearly}
        self._live = secret_key.startswith(("sk_live_", "rk_live_"))

    @property
    def mode(self) -> Literal["test", "live"]:
        return "live" if self._live else "test"

    def _call(self, fn, *args, **kwargs) -> dict:
        try:
            return fn(*args, **kwargs).to_dict()
        except stripe.StripeError as error:
            raise BillingUnavailable(str(error)) from error

    def plans(self) -> list[Plan]:
        plans = []
        for interval, price_id in self._prices.items():
            price = self._call(self._client.v1.prices.retrieve, price_id)
            plans.append(Plan(interval=interval, amount=price["unit_amount"], currency=price["currency"]))
        return plans

    def create_checkout(self, *, interval: str, user_id: str, email: str, customer_id: str | None, success_url: str,
                        cancel_url: str) -> tuple[str, str]:
        params: dict = {
            "mode": "subscription",
            "line_items": [{"price": self._prices[interval], "quantity": 1}],
            "client_reference_id": user_id,
            "metadata": {"user_id": user_id},
            "subscription_data": {"metadata": {"user_id": user_id}},
            "locale": "fr",
            "billing_address_collection": "required",
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
        if customer_id:
            params["customer"] = customer_id
            params["customer_update"] = {"address": "auto", "name": "auto"}
        else:
            params["customer_email"] = email
        session = self._call(self._client.v1.checkout.sessions.create, params=params)
        return session["id"], session["url"]

    def checkout_session(self, session_id: str) -> CheckoutInfo | None:
        try:
            s = self._client.v1.checkout.sessions.retrieve(session_id).to_dict()
        except stripe.InvalidRequestError:
            return None  # identifiant inconnu ou mal formé
        except stripe.StripeError as error:
            raise BillingUnavailable(str(error)) from error
        sub = s.get("subscription")
        return CheckoutInfo(session_id=s["id"], user_id=s.get("client_reference_id"), customer_id=s.get("customer"),
                            subscription_id=sub.get("id") if isinstance(sub, dict) else sub)

    def subscription(self, subscription_id: str) -> StripeSubscription:
        return subscription_from_dict(self._call(self._client.v1.subscriptions.retrieve, subscription_id))

    def portal(self, customer_id: str, return_url: str) -> str:
        return self._call(self._client.v1.billing_portal.sessions.create,
                          params={"customer": customer_id, "return_url": return_url})["url"]

    def cancel_now(self, subscription_id: str) -> None:
        try:
            self._client.v1.subscriptions.cancel(subscription_id)
        except stripe.InvalidRequestError as error:
            if getattr(error, "code", None) != "resource_missing" and "canceled" not in str(error):
                raise BillingUnavailable(str(error)) from error  # déjà résilié ou inconnu : rien à faire
        except stripe.StripeError as error:
            raise BillingUnavailable(str(error)) from error

    def update_customer_email(self, customer_id: str, email: str) -> None:
        self._call(self._client.v1.customers.update, customer_id, params={"email": email})

    def parse_event(self, payload: bytes, signature: str | None) -> StripeEventIn:
        if not signature:
            raise InvalidSignature("signature absente")
        try:
            stripe.WebhookSignature.verify_header(payload.decode("utf-8"), signature, self._webhook_secret,
                                                  tolerance=TOLERANCE_SECONDS)
        except stripe.SignatureVerificationError as error:
            raise InvalidSignature(str(error)) from error
        return event_from_dict(json.loads(payload))


def gateway_from_settings(settings) -> "StripeGateway | None":
    """Stripe si les quatre variables sont renseignées, sinon None (spec 7)."""
    if not settings.stripe_configured:
        return None
    return StripeGateway(secret_key=settings.stripe_secret_key, webhook_secret=settings.stripe_webhook_secret,
                         price_monthly=settings.stripe_price_monthly, price_yearly=settings.stripe_price_yearly)
