import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Subscription(Base):
    """Abonnement Stripe d'un compte (spec 1.1) : une ligne au plus, écrite uniquement à partir de l'état lu chez Stripe."""

    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    stripe_customer_id: Mapped[str] = mapped_column(String(255), unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    status: Mapped[str] = mapped_column(String(20))
    interval: Mapped[str | None] = mapped_column(String(5))  # month | year
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    renewal_notice_sent_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StripeEvent(Base):
    """Événements Stripe déjà traités (spec 1.2) : un événement livré deux fois n'est appliqué qu'une fois."""

    __tablename__ = "stripe_events"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    type: Mapped[str] = mapped_column(String(100))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class BillingConsent(Base):
    """Preuve des accords donnés avant le paiement (spec 1.3)."""

    __tablename__ = "billing_consents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    cgv_version: Mapped[str] = mapped_column(String(20))
    withdrawal_waiver: Mapped[bool] = mapped_column(Boolean)
    interval: Mapped[str] = mapped_column(String(5))
    checkout_session_id: Mapped[str | None] = mapped_column(String(255))
    ip: Mapped[str | None] = mapped_column(String(64))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StripeCancellation(Base):
    """Abonnements à résilier chez Stripe (compte supprimé, ou abonnement payé en double) et pages de paiement à fermer
    (identifiant `cs_…`, compte supprimé pendant un paiement) : aucune donnée personnelle."""

    __tablename__ = "stripe_cancellations"

    subscription_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
