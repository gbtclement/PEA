from datetime import datetime

from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FxRate(Base):
    """Valeur en euros d'une unité de devise, mise à jour chaque jour depuis Yahoo."""

    __tablename__ = "fx_rates"

    currency: Mapped[str] = mapped_column(String(8), primary_key=True)
    rate_to_eur: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
