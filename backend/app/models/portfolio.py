from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.services.fees import DEFAULT_GRID_JSON


class Order(Base):
    """Ordre saisi à la main. Prix et frais en euros."""

    __tablename__ = "orders"
    __table_args__ = (Index("ix_orders_user_date", "user_id", "trade_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id", ondelete="RESTRICT"), index=True)
    trade_date: Mapped[date] = mapped_column(Date)
    side: Mapped[str] = mapped_column(String(4))  # buy | sell
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Float)
    fee: Mapped[float] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    min_orders_per_year: Mapped[int] = mapped_column(Integer, default=12)
    penalty_fee: Mapped[float] = mapped_column(Float, default=96.0)
    fee_grid: Mapped[list] = mapped_column(JSONB, default=lambda: list(DEFAULT_GRID_JSON))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
