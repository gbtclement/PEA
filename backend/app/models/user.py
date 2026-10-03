import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Uuid, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

# Adresse provisoire de l'ancien utilisateur unique « Moi », reprise par ADMIN_EMAIL au démarrage.
LEGACY_EMAIL = "moi@pea-radar.invalid"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)  # toujours en minuscules
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True)
    role: Mapped[str] = mapped_column(String(10), default="user", server_default="user")  # user | admin
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terms_version: Mapped[str | None] = mapped_column(String(20))
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    inactivity_warned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Chargé avec le compte (jointure) : has_premium est lu à chaque requête.
    subscription: Mapped["Subscription | None"] = relationship(lazy="joined", passive_deletes=True)  # noqa: F821

    @property
    def has_password(self) -> bool:
        return self.password_hash is not None

    @property
    def has_google(self) -> bool:
        return self.google_sub is not None

    @property
    def terms_outdated(self) -> bool:
        from app.core.terms import TERMS_VERSION

        return self.terms_version != TERMS_VERSION

    @property
    def has_premium(self) -> bool:
        """Accès à l'assistant et aux prévisions : admin, Premium offert ou abonnement actif (spec 1.5)."""
        return self.premium_source != "none"

    @property
    def premium_source(self) -> str:
        from app.services.billing.access import premium_source

        return premium_source(self)
