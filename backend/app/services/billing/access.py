"""Qui est Premium (spec 1.5). Aucun appel à Stripe : l'état vient de la table `subscriptions`."""
from typing import Literal

from app.models import Subscription, User

ACCESS_STATUSES = frozenset({"active", "past_due", "trialing"})  # past_due : l'accès continue pendant les relances
PremiumSource = Literal["admin", "offered", "subscription", "none"]


def subscription_gives_access(sub: Subscription | None) -> bool:
    return sub is not None and sub.status in ACCESS_STATUSES


def premium_source(user: User) -> PremiumSource:
    if user.role == "admin":
        return "admin"
    if user.is_premium:
        return "offered"
    if subscription_gives_access(user.subscription):
        return "subscription"
    return "none"
