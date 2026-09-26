from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Security(TimestampMixin, Base):
    __tablename__ = "securities"

    id: Mapped[int] = mapped_column(primary_key=True)
    isin: Mapped[str | None] = mapped_column(String(12), unique=True)
    yahoo_ticker: Mapped[str] = mapped_column(String(32), unique=True)
    symbol: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(255), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # stock | etf | index
    market: Mapped[str] = mapped_column(String(64))
    country: Mapped[str | None] = mapped_column(String(2))
    sector: Mapped[str | None] = mapped_column(String(128))
    industry: Mapped[str | None] = mapped_column(String(128))
    eligibility: Mapped[str] = mapped_column(String(16), default="a_verifier", index=True)
    eligibility_source: Mapped[str] = mapped_column(String(16), default="auto")
    eligibility_override: Mapped[str | None] = mapped_column(String(16))
    active: Mapped[bool] = mapped_column(default=True)
