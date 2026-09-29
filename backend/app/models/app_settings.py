import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AppSettings(Base):
    """Réglages communs à toute l'application, modifiés dans l'onglet Admin. Une seule ligne (id = 1)."""

    __tablename__ = "app_settings"
    __table_args__ = (CheckConstraint("id = 1", name="app_settings_single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    ai_model: Mapped[str] = mapped_column(String(64), default="claude-opus-5", server_default="claude-opus-5")
    ai_monthly_cost_limit_usd: Mapped[float] = mapped_column(Float, default=5.0, server_default="5")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AiUsage(Base):
    """Coût de l'assistant cumulé par utilisateur et par mois (heure de Paris).

    Séparé des conversations : supprimer une conversation ne rend pas de budget.
    """

    __tablename__ = "ai_usage"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    month: Mapped[str] = mapped_column(String(7), primary_key=True)  # AAAA-MM
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
