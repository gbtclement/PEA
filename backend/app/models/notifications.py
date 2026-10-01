import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NotificationPrefs(Base):
    """Choix des mails N1 à N6. Pas de ligne tant que le membre n'a rien réglé : valeurs par défaut (spec 5.1)."""

    __tablename__ = "notification_prefs"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    price_move: Mapped[bool] = mapped_column(default=True, server_default=text("true"))       # N1
    price_alert: Mapped[bool] = mapped_column(default=True, server_default=text("true"))      # N2
    daily_recap: Mapped[bool] = mapped_column(default=False, server_default=text("false"))    # N3
    weekly_recap: Mapped[bool] = mapped_column(default=False, server_default=text("false"))   # N4
    order_reminder: Mapped[bool] = mapped_column(default=True, server_default=text("true"))   # N5
    score_change: Mapped[bool] = mapped_column(default=False, server_default=text("false"))   # N6
    move_threshold_pct: Mapped[float] = mapped_column(Float, default=5.0, server_default="5")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PriceAlert(Base):
    """Seuil de prix personnel (N2), dans la devise du titre. Désactivée une fois déclenchée."""

    __tablename__ = "price_alerts"
    __table_args__ = (Index("ix_price_alerts_active", "active", "security_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"))
    direction: Mapped[str] = mapped_column(String(5))  # above | below
    price: Mapped[float] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScoreSnapshot(Base):
    """Score de chaque titre et rang dans le top 10, photographiés chaque soir (N4, N6). Gardés 14 jours."""

    __tablename__ = "score_snapshots"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"), primary_key=True)
    total: Mapped[float] = mapped_column(Float)
    top_rank: Mapped[int | None] = mapped_column(Integer)


class MoveNotice(Base):
    """Titre déjà signalé par N1 à ce membre ce jour-là (au plus une fois par titre et par jour). Gardé 7 jours."""

    __tablename__ = "move_notices"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
