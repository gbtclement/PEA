from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SecurityScore(Base):
    """Score mixte et indicateurs précalculés par la tâche `scores` du worker."""

    __tablename__ = "scores"

    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"), primary_key=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    total: Mapped[float | None] = mapped_column(Float, index=True)
    technical: Mapped[float | None] = mapped_column(Float)
    fundamental: Mapped[float | None] = mapped_column(Float)
    components: Mapped[list] = mapped_column(JSONB, default=list)
    available_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    liquid: Mapped[bool] = mapped_column(default=False)
    history_days: Mapped[int] = mapped_column(default=0)
    avg_turnover_eur: Mapped[float] = mapped_column(Float, default=0.0)
    eligible_for_top: Mapped[bool] = mapped_column(default=False, index=True)
    perf_1w: Mapped[float | None] = mapped_column(Float)
    perf_1m: Mapped[float | None] = mapped_column(Float)
    perf_3m: Mapped[float | None] = mapped_column(Float)
    perf_1y: Mapped[float | None] = mapped_column(Float)
    sparkline: Mapped[list] = mapped_column(JSONB, default=list)
