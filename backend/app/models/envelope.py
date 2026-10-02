from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SecurityEnvelope(Base):
    """Statut d'un titre pour une enveloppe à règle (pea, pea_pme). Le compte-titres n'est pas stocké : il accepte tout."""

    __tablename__ = "security_envelopes"
    __table_args__ = (Index("ix_security_envelopes_envelope_status", "envelope", "status"),)

    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"), primary_key=True)
    envelope: Mapped[str] = mapped_column(String(16), primary_key=True)
    status: Mapped[str] = mapped_column(String(16))  # eligible | a_verifier | non_eligible
    source: Mapped[str] = mapped_column(String(16), default="auto")  # auto | seed | manual
    override: Mapped[str | None] = mapped_column(String(16))
