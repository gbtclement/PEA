"""Seul point de contact avec Stripe (spec 7) : types normalisés, lecture des objets Stripe, interface.

Les objets Stripe arrivent en dictionnaires (JSON du webhook, ou `to_dict()` de la bibliothèque) ; les fonctions de
lecture sont pures et acceptent l'ancien et le nouveau format de l'API (Rulings 3 et 4).
"""
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol


class BillingUnavailable(Exception):
    """Stripe injoignable ou en erreur : rien n'est enregistré, l'utilisateur est invité à réessayer."""


class BillingRejected(BillingUnavailable):
    """Refus définitif de Stripe (objet inconnu, clé révoquée…) : réessayer ne changera rien."""


class InvalidSignature(Exception):
    """Webhook sans signature Stripe valide."""


@dataclass(frozen=True)
class StripeSubscription:
    id: str
    customer_id: str
    user_id: str | None
    status: str
    interval: str | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    ends_at: datetime | None  # date de fin programmée (cancel_at), sinon None
    latest_invoice: str | None
    price_amount: int | None  # centimes
    currency: str | None


@dataclass(frozen=True)
class Plan:
    interval: str  # month | year
    amount: int  # centimes, TTC
    currency: str


@dataclass(frozen=True)
class CheckoutInfo:
    session_id: str
    user_id: str | None
    customer_id: str | None
    subscription_id: str | None


@dataclass(frozen=True)
class StripeEventIn:
    id: str
    type: str
    subscription_id: str | None
    customer_id: str | None
    user_id: str | None


def _id(value) -> str | None:
    """Un identifiant, ou l'objet « déplié » qui le contient."""
    if isinstance(value, dict):
        return value.get("id")
    return value or None


def _ts(value) -> datetime | None:
    return datetime.fromtimestamp(value, UTC) if value else None


def subscription_from_dict(data: dict) -> StripeSubscription:
    items = (data.get("items") or {}).get("data") or [{}]
    item = items[0]
    price = item.get("price") or {}
    period_end = item.get("current_period_end") or data.get("current_period_end")
    cancel_at = data.get("cancel_at")
    return StripeSubscription(
        id=data["id"], customer_id=_id(data.get("customer")), user_id=(data.get("metadata") or {}).get("user_id"),
        status=data["status"], interval=(price.get("recurring") or {}).get("interval"),
        current_period_end=_ts(period_end), cancel_at_period_end=bool(data.get("cancel_at_period_end") or cancel_at),
        ends_at=_ts(cancel_at), latest_invoice=_id(data.get("latest_invoice")),
        price_amount=price.get("unit_amount"), currency=price.get("currency"),
    )


def event_from_dict(data: dict) -> StripeEventIn:
    obj = data["data"]["object"]
    kind = obj.get("object")
    user_id = (obj.get("metadata") or {}).get("user_id")
    if kind == "checkout.session":
        subscription_id, user_id = _id(obj.get("subscription")), obj.get("client_reference_id") or user_id
    elif kind == "subscription":
        subscription_id = obj["id"]
    elif kind == "invoice":
        details = (obj.get("parent") or {}).get("subscription_details") or {}
        subscription_id = _id(details.get("subscription")) or _id(obj.get("subscription"))
        user_id = (details.get("metadata") or {}).get("user_id")
    else:
        subscription_id = None
    return StripeEventIn(id=data["id"], type=data["type"], subscription_id=subscription_id,
                         customer_id=_id(obj.get("customer")), user_id=user_id)


class BillingGateway(Protocol):
    @property
    def mode(self) -> Literal["test", "live"]: ...

    def plans(self) -> list[Plan]: ...

    def create_checkout(self, *, interval: str, user_id: str, email: str, customer_id: str | None, success_url: str,
                        cancel_url: str) -> tuple[str, str]: ...

    def checkout_session(self, session_id: str) -> CheckoutInfo | None: ...

    def subscription(self, subscription_id: str) -> StripeSubscription: ...

    def portal(self, customer_id: str, return_url: str) -> str: ...

    def cancel_now(self, subscription_id: str) -> None: ...

    def expire_checkout(self, session_id: str) -> None: ...

    def update_customer_email(self, customer_id: str, email: str) -> None: ...

    def parse_event(self, payload: bytes, signature: str | None) -> StripeEventIn: ...
