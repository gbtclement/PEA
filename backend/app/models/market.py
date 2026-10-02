from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SecurityQuote(Base):
    """Dernier cours connu d'un titre."""

    __tablename__ = "quotes"

    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"), primary_key=True)
    price: Mapped[float] = mapped_column(Float)
    previous_close: Mapped[float | None] = mapped_column(Float)
    change_pct: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(BigInteger)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DailyPrice(Base):
    __tablename__ = "daily_prices"

    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(BigInteger)


class SecurityFundamentals(Base):
    """Ratios en fraction (0,0328 = 3,28 %), dette/capitaux propres en ratio (0,53)."""

    __tablename__ = "fundamentals"

    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"), primary_key=True)
    pe: Mapped[float | None] = mapped_column(Float)
    eps: Mapped[float | None] = mapped_column(Float)
    earnings_growth: Mapped[float | None] = mapped_column(Float)
    revenue_growth: Mapped[float | None] = mapped_column(Float)
    debt_to_equity: Mapped[float | None] = mapped_column(Float)
    profit_margin: Mapped[float | None] = mapped_column(Float)
    dividend_yield: Mapped[float | None] = mapped_column(Float)
    market_cap: Mapped[float | None] = mapped_column(Float)
    employees: Mapped[int | None] = mapped_column(Integer)
    revenue: Mapped[float | None] = mapped_column(Float)  # chiffre d'affaires annuel, en `revenue_currency`
    revenue_currency: Mapped[str | None] = mapped_column(String(3))
    currency: Mapped[str | None] = mapped_column(String(3))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
