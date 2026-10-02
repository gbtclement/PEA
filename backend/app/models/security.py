from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.envelope import SecurityEnvelope


class Security(TimestampMixin, Base):
    __tablename__ = "securities"

    id: Mapped[int] = mapped_column(primary_key=True)
    isin: Mapped[str | None] = mapped_column(String(12), unique=True)
    yahoo_ticker: Mapped[str] = mapped_column(String(32), unique=True)
    symbol: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(255), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # stock | etf | index
    market: Mapped[str] = mapped_column(String(64))
    currency: Mapped[str | None] = mapped_column(String(8))  # devise de cotation (GBp possible) ; vide = selon la place
    source: Mapped[str | None] = mapped_column(String(16))  # liste d'origine : euronext, euronext_etf, us, xetra, six, nordic, seed
    country: Mapped[str | None] = mapped_column(String(2))
    sector: Mapped[str | None] = mapped_column(String(128))
    industry: Mapped[str | None] = mapped_column(String(128))
    active: Mapped[bool] = mapped_column(default=True)
    history_complete: Mapped[bool] = mapped_column(default=False)  # cours chargés depuis la première cotation
    envelopes: Mapped[list[SecurityEnvelope]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", passive_deletes=True, order_by=SecurityEnvelope.envelope,
    )

    def envelope(self, code: str) -> SecurityEnvelope | None:
        return next((e for e in self.envelopes if e.envelope == code), None)

    def envelope_status(self, code: str) -> str | None:
        row = self.envelope(code)
        return row.status if row else None

    @property
    def eligible_envelopes(self) -> list[str]:
        """Codes des enveloppes à règle où le titre est éligible (« pea » avant « pea_pme »)."""
        return [e.envelope for e in self.envelopes if e.status == "eligible"]
