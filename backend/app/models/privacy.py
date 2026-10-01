import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DataExport(Base):
    """Export des données d'un compte (spec 6.4) : préparé par le worker, téléchargeable 7 jours, connecté."""

    __tablename__ = "data_exports"
    __table_args__ = (
        Index("uq_data_exports_one_pending", "user_id", unique=True, postgresql_where=text("status = 'pending'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(10), default="pending", server_default="pending")  # pending | ready | failed
    content: Mapped[str | None] = mapped_column(Text)  # JSON, en base plutôt qu'en fichier : api et worker n'ont pas de volume commun
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
