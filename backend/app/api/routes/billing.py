"""Abonnement Premium (spec 3) : prix, résumé, passage en caisse. Le webhook et /sync, /portal suivent (Tasks 6 et 7)."""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import PLANS_CACHE, get_billing_gateway
from app.api.routes.auth import client_ip, fail
from app.core.config import get_settings
from app.core.current_user import get_current_user, get_now
from app.core.db import get_db
from app.core.security import truncate_ip
from app.core.terms import CGV_VERSION
from app.models import BillingConsent, User
from app.schemas.billing import CheckoutIn, PlanOut, PlansOut, RedirectOut, SubscriptionOut
from app.services import ratelimit
from app.services.billing.access import premium_source
from app.services.billing.gateway import BillingGateway, BillingUnavailable
from app.services.security_log import log_event

router = APIRouter(prefix="/billing", tags=["billing"])
GatewayDep = Annotated[BillingGateway | None, Depends(get_billing_gateway)]


def unavailable() -> HTTPException:
    return fail(503, "billing_unavailable", "Paiement indisponible, réessayez dans quelques minutes.")


def require_gateway(gateway: BillingGateway | None) -> BillingGateway:
    if gateway is None:
        raise fail(503, "billing_not_configured", "L'abonnement n'est pas encore disponible.")
    return gateway


def summary(user: User) -> SubscriptionOut:
    row = user.subscription
    return SubscriptionOut(source=premium_source(user), status=row.status if row else None,
                           interval=row.interval if row else None,
                           current_period_end=row.current_period_end if row else None,
                           cancel_at_period_end=bool(row and row.cancel_at_period_end), has_customer=row is not None)


def _base_url() -> str:
    return get_settings().public_base_url.rstrip("/")


@router.get("/plans", response_model=PlansOut)
def billing_plans(gateway: GatewayDep) -> PlansOut:
    if gateway is None:
        return PlansOut(configured=False, plans=[], yearly_saving_pct=None)
    try:
        plans = PLANS_CACHE.get_or_set("plans", gateway.plans)
    except BillingUnavailable:
        return PlansOut(configured=True, plans=[], yearly_saving_pct=None)
    by_interval = {p.interval: p for p in plans}
    month, year = by_interval.get("month"), by_interval.get("year")
    saving = round((1 - year.amount / (12 * month.amount)) * 100) if month and year and month.amount else None
    return PlansOut(configured=True, plans=[PlanOut(interval=p.interval, amount=p.amount, currency=p.currency) for p in plans],
                    yearly_saving_pct=saving)


@router.get("/subscription", response_model=SubscriptionOut)
def billing_subscription(user: User = Depends(get_current_user)) -> SubscriptionOut:
    return summary(user)


@router.post("/checkout", response_model=RedirectOut)
def billing_checkout(payload: CheckoutIn, request: Request, gateway: GatewayDep, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user), now: datetime = Depends(get_now)) -> RedirectOut:
    gateway = require_gateway(gateway)
    source = premium_source(user)
    if source == "subscription":
        raise fail(409, "already_premium", "Vous êtes déjà abonné : gérez votre abonnement depuis les Réglages.")
    if source in ("offered", "admin"):
        raise fail(409, "premium_offered", "Premium vous est déjà offert : inutile de vous abonner.")
    if not (payload.accept_cgv and payload.waive_withdrawal):
        raise fail(422, "consent_required", "Cochez les deux cases pour continuer.")
    if ratelimit.over(db, "checkout_user", str(user.id), now):
        raise fail(429, "too_many_attempts", "Trop de tentatives de paiement : réessayez dans une heure.")
    ratelimit.record(db, "checkout_user", str(user.id), now)
    ip = client_ip(request)
    consent = BillingConsent(user_id=user.id, cgv_version=CGV_VERSION, withdrawal_waiver=True, interval=payload.interval,
                             ip=truncate_ip(ip), accepted_at=now)
    db.add(consent)
    log_event(db, "billing_consent", now=now, user_id=user.id, ip=ip,
              details={"cgv_version": CGV_VERSION, "interval": payload.interval})
    db.commit()  # la preuve de l'accord reste, même si Stripe ne répond pas (spec 3.2)
    customer_id = user.subscription.stripe_customer_id if user.subscription else None
    try:
        session_id, url = gateway.create_checkout(
            interval=payload.interval, user_id=str(user.id), email=user.email, customer_id=customer_id,
            success_url=f"{_base_url()}/premium/merci?session_id={{CHECKOUT_SESSION_ID}}", cancel_url=f"{_base_url()}/premium")
    except BillingUnavailable:
        raise unavailable()
    consent.checkout_session_id = session_id
    db.commit()
    return RedirectOut(url=url)
