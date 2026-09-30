"""Événements Stripe (spec 4.1) : l'état est toujours relu chez Stripe, l'ordre d'arrivée n'a donc pas d'importance."""
import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StripeEvent, Subscription, User
from app.services.billing.access import ACCESS_STATUSES
from app.services.billing.gateway import BillingGateway, StripeEventIn, StripeSubscription
from app.services.billing.state import apply_subscription

logger = logging.getLogger(__name__)
HANDLED_TYPES = frozenset({
    "checkout.session.completed", "customer.subscription.created", "customer.subscription.updated",
    "customer.subscription.deleted", "invoice.paid", "invoice.payment_failed",
})


def _user(db: Session, event: StripeEventIn, sub: StripeSubscription) -> User | None:
    for raw in (event.user_id, sub.user_id):
        try:
            user = db.get(User, uuid.UUID(raw)) if raw else None
        except ValueError:
            user = None
        if user is not None:
            return user
    row = db.scalar(select(Subscription).where(Subscription.stripe_customer_id == (event.customer_id or sub.customer_id)))
    return db.get(User, row.user_id) if row else None


def handle_event(db: Session, gateway: BillingGateway, event: StripeEventIn, *, now: datetime) -> None:
    """Pas de commit ici. BillingUnavailable remonte : Stripe renverra l'événement plus tard."""
    if db.get(StripeEvent, event.id) is not None:
        return
    if event.type in HANDLED_TYPES and event.subscription_id:
        sub = gateway.subscription(event.subscription_id)
        user = _user(db, event, sub)
        if user is not None:
            apply_subscription(db, user, sub, now=now)
        elif sub.status in ACCESS_STATUSES:  # compte supprimé entre-temps : plus aucun prélèvement
            logger.warning("Abonnement Stripe %s sans compte : résiliation", sub.id)
            gateway.cancel_now(sub.id)
    db.add(StripeEvent(id=event.id, type=event.type, received_at=now))
