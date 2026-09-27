from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ForecastRun(Base):
    """Un calcul complet des statistiques des signaux et du test sur l'année écoulée (seul le dernier sert)."""

    __tablename__ = "forecast_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_until: Mapped[date | None] = mapped_column(Date)
    cutoff: Mapped[date | None] = mapped_column(Date)
    round_trip_cost: Mapped[float] = mapped_column(Float)
    stats: Mapped[list] = mapped_column(JSONB, default=list)      # SignalStat.to_dict(), référence comprise
    backtest: Mapped[dict] = mapped_column(JSONB, default=dict)   # horizon → BacktestResult.to_dict()


class Forecast(Base):
    """Prédiction d'un titre pour un horizon, enregistrée le matin puis vérifiée quand l'horizon est atteint."""

    __tablename__ = "forecasts"
    __table_args__ = (
        UniqueConstraint("security_id", "as_of", "horizon", name="uq_forecast_security_day_horizon"),
        Index("ix_forecasts_as_of_horizon", "as_of", "horizon"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"), index=True)
    as_of: Mapped[date] = mapped_column(Date)            # séance dont la clôture sert de point de départ
    horizon: Mapped[str] = mapped_column(String(2))      # 1d | 1w | 1m
    expected_return: Mapped[float] = mapped_column(Float)
    prob_up: Mapped[float] = mapped_column(Float)
    reliability: Mapped[str] = mapped_column(String(8))
    signals: Mapped[list] = mapped_column(JSONB, default=list)
    rank: Mapped[int] = mapped_column(Integer)           # 1 = meilleur gain attendu ce jour-là pour cet horizon
    base_close: Mapped[float] = mapped_column(Float)
    actual_return: Mapped[float | None] = mapped_column(Float)
    resolved_on: Mapped[date | None] = mapped_column(Date)
