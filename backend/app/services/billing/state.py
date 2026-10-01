"""Applique l'état d'un abonnement lu chez Stripe (spec 4.2) : une seule fonction pour le webhook, /sync et la nuit.

Les mails partent quand l'accès ou la résiliation change ; `dedupe_key` empêche un doublon si le même état revient.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import StripeCancellation, Subscription, User
from app.services.billing.access import ACCESS_STATUSES, subscription_gives_access
from app.services.billing.gateway import StripeSubscription
from app.services.mail.outbox import enqueue
from app.services.security_log import log_event

PARIS = ZoneInfo("Europe/Paris")
INTERVAL_LABELS = {"month": "mensuel", "year": "annuel"}


def _day(value: datetime | None) -> date | None:
    return value.astimezone(PARIS).date() if value else None


def _amount(amount: int | None, currency: str | None) -> str | None:
    if amount is None:
        return None
    number = f"{amount / 100:,.2f}".replace(",", " ").replace(".", ",")
    return f"{number} €" if (currency or "eur").lower() == "eur" else f"{number} {currency.upper()}"


def mail_context(user: User, row: Subscription, amount: int | None = None, currency: str | None = None) -> dict:
    base = get_settings().public_base_url.rstrip("/")
    period_end = _day(row.current_period_end)
    return {
        "first_name": user.first_name, "interval_label": INTERVAL_LABELS.get(row.interval or "", ""),
        "period_end": period_end, "ends_on": period_end,
        "renews_on": period_end.strftime("%d/%m/%Y") if period_end else "",
        "amount": _amount(amount, currency),
        "manage_url": f"{base}/reglages#abonnement", "premium_url": f"{base}/premium", "cgv_url": f"{base}/cgv",
    }


def apply_subscription(db: Session, user: User, sub: StripeSubscription, *, now: datetime) -> Subscription:
    row = db.get(Subscription, user.id)
    if (row is not None and row.stripe_subscription_id not in (None, sub.id) and sub.status not in ACCESS_STATUSES
            and subscription_gives_access(row)):
        return row  # Ruling 5 : un essai raté n'écrase pas l'abonnement en cours
    if (row is not None and row.stripe_subscription_id not in (None, sub.id) and sub.status in ACCESS_STATUSES
            and subscription_gives_access(row)):
        # Payé deux fois (deuxième onglet) : le doublon est résilié par la file, l'admin rembourse depuis Stripe.
        if db.get(StripeCancellation, sub.id) is None:
            db.add(StripeCancellation(subscription_id=sub.id))
            log_event(db, "duplicate_subscription", now=now, user_id=user.id, details={"subscription_id": sub.id})
        return row
    same = row is not None and row.stripe_subscription_id == sub.id
    had_access = subscription_gives_access(row)
    was_canceling = same and row.cancel_at_period_end
    if row is None:
        row = Subscription(user_id=user.id, stripe_customer_id=sub.customer_id, status=sub.status)
        db.add(row)
    row.stripe_customer_id, row.stripe_subscription_id, row.status = sub.customer_id, sub.id, sub.status
    row.interval, row.current_period_end = sub.interval, sub.current_period_end
    row.cancel_at_period_end, row.updated_at = sub.cancel_at_period_end, now
    db.flush()
    db.refresh(user, ["subscription"])
    has_access = sub.status in ACCESS_STATUSES
    context = mail_context(user, row, sub.price_amount, sub.currency)
    if sub.ends_at is not None:
        context["ends_on"] = _day(sub.ends_at)

    def send(kind: str, key: str) -> None:
        enqueue(db, kind, to=user.email, user_id=user.id, context=context, dedupe_key=key)

    if has_access and not had_access:
        send("premium_started", f"premium_started:{sub.id}")
        log_event(db, "subscription_started", now=now, user_id=user.id, details={"interval": sub.interval})
    if has_access and sub.cancel_at_period_end and not was_canceling:
        send("premium_canceling", f"premium_cancel:{sub.id}:{context['ends_on']}")
    if sub.status == "past_due" and sub.latest_invoice:
        send("payment_failed", f"payment_failed:{sub.id}:{sub.latest_invoice}")
    if had_access and not has_access:
        send("premium_ended", f"premium_ended:{sub.id}")
        log_event(db, "subscription_ended", now=now, user_id=user.id, details={"status": sub.status})
    return row
