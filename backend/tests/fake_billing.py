from dataclasses import replace
from datetime import UTC, datetime

from app.services.billing.gateway import (
    BillingRejected, BillingUnavailable, CheckoutInfo, InvalidSignature, Plan, StripeEventIn, StripeSubscription,
)


class FakeBilling:
    """Remplace Stripe. `subs` = abonnements « chez Stripe » ; `down = True` simule une panne ; la signature valide est
    « bonne-signature », et le corps du webhook est un JSON {"id", "type", "subscription_id", "customer_id", "user_id"}."""

    mode = "test"

    def __init__(self) -> None:
        self.subs: dict[str, StripeSubscription] = {}
        self.sessions: dict[str, CheckoutInfo] = {}
        self.checkouts: list[dict] = []
        self.canceled: list[str] = []
        self.expired: list[str] = []
        self.rejected: set[str] = set()  # abonnements que Stripe refuse définitivement (erreur 4xx)
        self.email_fails = False
        self.emails: dict[str, str] = {}
        self.portals: list[str] = []
        self.down = False
        self.prices = [Plan("month", 499, "eur"), Plan("year", 4900, "eur")]

    def _check(self) -> None:
        if self.down:
            raise BillingUnavailable("Stripe injoignable (faux)")

    def put(self, sub_id: str = "sub_1", *, customer_id: str = "cus_1", user_id: str | None = None, status: str = "active",
            interval: str = "month", period_end: datetime | None = None, cancel: bool = False,
            latest_invoice: str | None = "in_1") -> StripeSubscription:
        sub = StripeSubscription(id=sub_id, customer_id=customer_id, user_id=user_id, status=status, interval=interval,
                                 current_period_end=period_end or datetime(2026, 11, 1, tzinfo=UTC),
                                 cancel_at_period_end=cancel, ends_at=None, latest_invoice=latest_invoice,
                                 price_amount=499 if interval == "month" else 4900, currency="eur")
        self.subs[sub_id] = sub
        return sub

    def update(self, sub_id: str, **changes) -> StripeSubscription:
        self.subs[sub_id] = replace(self.subs[sub_id], **changes)
        return self.subs[sub_id]

    def plans(self) -> list[Plan]:
        self._check()
        return list(self.prices)

    def create_checkout(self, *, interval, user_id, email, customer_id, success_url, cancel_url):
        self._check()
        session_id = f"cs_{len(self.checkouts) + 1}"
        self.checkouts.append(dict(interval=interval, user_id=user_id, email=email, customer_id=customer_id,
                                   success_url=success_url, cancel_url=cancel_url, session_id=session_id))
        return session_id, f"https://checkout.stripe.test/{session_id}"

    def checkout_session(self, session_id):
        self._check()
        return self.sessions.get(session_id)

    def subscription(self, subscription_id):
        self._check()
        if subscription_id in self.rejected:
            raise BillingRejected(f"No such subscription: {subscription_id}")
        return self.subs[subscription_id]

    def portal(self, customer_id, return_url):
        self._check()
        self.portals.append(customer_id)
        return f"https://billing.stripe.test/{customer_id}"

    def cancel_now(self, subscription_id):
        self._check()
        self.canceled.append(subscription_id)
        if subscription_id in self.subs:
            self.update(subscription_id, status="canceled")

    def expire_checkout(self, session_id):
        self._check()
        self.expired.append(session_id)

    def update_customer_email(self, customer_id, email):
        self._check()
        if self.email_fails:
            raise BillingRejected("adresse refusée (faux)")
        self.emails[customer_id] = email

    def parse_event(self, payload: bytes, signature):
        import json

        if signature != "bonne-signature":
            raise InvalidSignature("fausse signature")
        return StripeEventIn(**json.loads(payload))
