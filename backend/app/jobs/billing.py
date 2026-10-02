"""Abonnements côté worker (spec 4.3, 5 P5, Ruling 1). Chaque ligne a son point de sauvegarde : une erreur n'arrête pas
les autres."""
import logging
from datetime import timedelta

from sqlalchemy import or_, select

from app.jobs.context import JobContext
from app.models import StripeCancellation, Subscription, User
from app.services.billing.gateway import BillingUnavailable
from app.services.billing.state import apply_subscription, mail_context
from app.services.mail.outbox import enqueue

logger = logging.getLogger(__name__)
ENDED_RECENTLY = timedelta(days=7)
RENEWAL_NOTICE = timedelta(days=30)
FINISHED = ("canceled", "incomplete_expired")


def sync_subscriptions(ctx: JobContext) -> int:
    """Chaque nuit : relit chez Stripe les abonnements vivants (et ceux terminés depuis moins de 7 jours), et met à jour le
    mail des clients Stripe (Ruling 2)."""
    if ctx.billing is None:
        return 0
    now, done = ctx.now(), 0
    with ctx.session_factory() as db:
        rows = db.scalars(select(Subscription).where(
            Subscription.stripe_subscription_id.is_not(None),
            or_(Subscription.status.not_in(FINISHED), Subscription.updated_at > now - ENDED_RECENTLY))).all()
        for row in rows:
            try:
                with db.begin_nested():
                    user = db.get(User, row.user_id)
                    apply_subscription(db, user, ctx.billing.subscription(row.stripe_subscription_id), now=now)
            except Exception:
                logger.exception("Synchronisation Stripe impossible pour %s", row.stripe_subscription_id)
                continue
            done += 1
            try:  # à part : une adresse refusée par Stripe n'annule pas l'état relu juste avant
                ctx.billing.update_customer_email(row.stripe_customer_id, user.email)
            except Exception:
                logger.exception("Mise à jour du mail Stripe impossible pour %s", row.stripe_customer_id)
        db.commit()
    return done


def _own_price(ctx: JobContext, subscription_id: str) -> tuple[int | None, str | None]:
    """Le prix de l'abonné lui-même (pas celui affiché aujourd'hui) : P5 doit l'annoncer exactement."""
    if ctx.billing is None:
        return None, None
    try:
        sub = ctx.billing.subscription(subscription_id)
    except BillingUnavailable:
        return None, None
    return sub.price_amount, sub.currency


def send_renewal_notices(ctx: JobContext) -> int:
    """Chaque matin : P5, 30 jours avant le renouvellement d'un abonnement annuel non résilié (article L215-1)."""
    now, sent = ctx.now(), 0
    with ctx.session_factory() as db:
        rows = db.scalars(select(Subscription).where(
            Subscription.interval == "year", Subscription.status == "active", Subscription.cancel_at_period_end.is_(False),
            Subscription.current_period_end > now, Subscription.current_period_end <= now + RENEWAL_NOTICE,
            or_(Subscription.renewal_notice_sent_for.is_(None),
                Subscription.renewal_notice_sent_for != Subscription.current_period_end))).all()
        for row in rows:
            amount, currency = _own_price(ctx, row.stripe_subscription_id)
            if amount is None:
                continue  # sans prix connu, P5 attend le lendemain
            user = db.get(User, row.user_id)
            enqueue(db, "renewal_reminder", to=user.email, user_id=user.id, context=mail_context(user, row, amount, currency),
                    dedupe_key=f"renewal:{row.stripe_subscription_id}:{row.current_period_end.date().isoformat()}")
            row.renewal_notice_sent_for = row.current_period_end
            sent += 1
        db.commit()
    return sent


def process_cancellations(ctx: JobContext) -> int:
    """Toutes les minutes : résilie chez Stripe les abonnements des comptes supprimés et les doublons, jusqu'à réussite (Ruling 1)."""
    if ctx.billing is None:
        return 0
    done = 0
    with ctx.session_factory() as db:
        for row in db.scalars(select(StripeCancellation).with_for_update(skip_locked=True)).all():
            try:
                if row.subscription_id.startswith("cs_"):  # page de paiement d'un compte supprimé
                    ctx.billing.expire_checkout(row.subscription_id)
                else:
                    ctx.billing.cancel_now(row.subscription_id)
            except BillingUnavailable as error:
                row.attempts += 1
                row.last_error = str(error)[:500]
                continue
            db.delete(row)
            done += 1
        db.commit()
    return done
