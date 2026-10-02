"""Prévisions court terme : prédictions du jour, statistiques des signaux et bulletin de notes."""
from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.current_user import get_current_user, require_premium
from app.core.db import get_db
from app.models import Forecast, Security, SecurityQuote, User
from app.repositories.forecasts import forecasts_for, latest_as_of, latest_run
from app.schemas.forecasts import (
    BacktestOut, ForecastListOut, ForecastRowOut, ForecastSecurityOut, HorizonForecastOut, RealTrackOut,
    SecurityForecastOut, SignalOut, SignalStatOut, SignalStatsOut, SignalStatsRowOut, TrackRecordOut,
)
from app.services.forecast.signals import SIGNALS
from app.services.forecast.stats import BASELINE, HORIZONS

router = APIRouter(tags=["forecasts"])
DbDep = Annotated[Session, Depends(get_db)]
TOP_PICKS = 10


def _no_horizons() -> dict:
    return {h: None for h in HORIZONS}


def _signals(keys: list[str]) -> list[SignalOut]:
    return [SignalOut(key=k, label=SIGNALS[k].label, bullish=SIGNALS[k].bullish) for k in keys if k in SIGNALS]


def _horizon(f: Forecast) -> HorizonForecastOut:
    return HorizonForecastOut(expected_return=f.expected_return, prob_up=f.prob_up, reliability=f.reliability, rank=f.rank)


def _signals_of(items: list[Forecast]) -> list[str]:
    # Tous les horizons partagent les mêmes signaux ; on garde la liste la plus complète par sécurité.
    return max(items, key=lambda f: len(f.signals)).signals if items else []


@router.get("/forecasts", response_model=ForecastListOut)
def list_forecasts(db: DbDep, _user: User = Depends(require_premium)) -> ForecastListOut:
    run = latest_run(db)
    cost = run.round_trip_cost if run else None
    as_of = latest_as_of(db)
    if as_of is None:
        return ForecastListOut(as_of=None, round_trip_cost=cost, rows=[])
    by_security: dict[int, list[Forecast]] = defaultdict(list)
    for f in forecasts_for(db, as_of):
        by_security[f.security_id].append(f)
    securities = {s.id: s for s in db.scalars(select(Security).where(Security.id.in_(by_security)))}
    quotes = {q.security_id: q for q in db.scalars(select(SecurityQuote).where(SecurityQuote.security_id.in_(by_security)))}
    rows = []
    for security_id, items in by_security.items():
        s, q = securities[security_id], quotes.get(security_id)
        rows.append(ForecastRowOut(
            security=ForecastSecurityOut(id=s.id, name=s.name, symbol=s.symbol, market=s.market, envelopes=s.eligible_envelopes,
                                         price=q.price if q else None, change_pct=q.change_pct if q else None),
            signals=_signals(_signals_of(items)),
            horizons=_no_horizons() | {f.horizon: _horizon(f) for f in items},
        ))
    rows.sort(key=lambda r: (r.horizons["1w"] is None, r.horizons["1w"].rank if r.horizons["1w"] else 0, r.security.name))
    return ForecastListOut(as_of=as_of, round_trip_cost=cost, rows=rows)


def _stat_out(stat: dict | None) -> SignalStatOut | None:
    return SignalStatOut(**{k: stat[k] for k in SignalStatOut.model_fields}) if stat else None


@router.get("/forecasts/signals", response_model=SignalStatsOut)
def signal_statistics(db: DbDep, _user: User = Depends(get_current_user)) -> SignalStatsOut:
    run = latest_run(db)
    if run is None:
        return SignalStatsOut(as_of=None, computed_at=None, round_trip_cost=None, signals=[], baseline=_no_horizons())
    stats = {(s["signal"], s["horizon"]): s for s in run.stats}
    rows = [
        SignalStatsRowOut(key=key, label=info.label, description=info.description, bullish=info.bullish,
                          horizons={h: _stat_out(stats.get((key, h))) for h in HORIZONS})
        for key, info in SIGNALS.items()
    ]
    return SignalStatsOut(as_of=run.data_until, computed_at=run.computed_at, round_trip_cost=run.round_trip_cost,
                          signals=rows, baseline={h: _stat_out(stats.get((BASELINE, h))) for h in HORIZONS})


def _real_track(db: Session, horizon: str, cost: float) -> RealTrackOut | None:
    """Prédictions réellement enregistrées puis vérifiées : les 10 meilleures prédictions de hausse de chaque jour.

    La comparaison porte sur la moyenne de tous les titres suivis (avec un signal) les mêmes jours. Calcul en SQL :
    le nombre de prédictions vérifiées grandit chaque jour.
    """
    resolved = (Forecast.horizon == horizon, Forecast.actual_return.is_not(None))
    day = (select(Forecast.as_of.label("day"), func.avg(Forecast.actual_return).label("mean"))
           .where(*resolved).group_by(Forecast.as_of).subquery())
    picks, mean, hit, hit_fees, baseline, first_day = db.execute(
        select(func.count(), func.avg(Forecast.actual_return),
               func.avg(case((Forecast.actual_return > 0, 1.0), else_=0.0)),
               func.avg(case((Forecast.actual_return > cost, 1.0), else_=0.0)),
               func.avg(day.c.mean), func.min(Forecast.as_of))
        .join(day, day.c.day == Forecast.as_of)
        .where(*resolved, Forecast.rank <= TOP_PICKS, Forecast.expected_return > 0)
    ).one()
    if not picks:
        return None
    return RealTrackOut(picks=picks, hit_rate=hit, hit_after_fees=hit_fees, mean_return=mean, mean_after_fees=mean - cost,
                        baseline_mean=baseline, edge=mean - baseline, first_day=first_day)


@router.get("/forecasts/track-record", response_model=TrackRecordOut)
def track_record(db: DbDep, _user: User = Depends(get_current_user)) -> TrackRecordOut:
    run = latest_run(db)
    if run is None:
        return TrackRecordOut(cutoff=None, round_trip_cost=None, simulated=_no_horizons(), real=_no_horizons())
    simulated = {h: BacktestOut(**run.backtest[h]) if run.backtest.get(h, {}).get("picks") else None for h in HORIZONS}
    real = {h: _real_track(db, h, run.round_trip_cost) for h in HORIZONS}
    return TrackRecordOut(cutoff=run.cutoff, round_trip_cost=run.round_trip_cost, simulated=simulated, real=real)


@router.get("/securities/{security_id}/forecast", response_model=SecurityForecastOut)
def security_forecast(security_id: int, db: DbDep, _user: User = Depends(require_premium)) -> SecurityForecastOut:
    if db.get(Security, security_id) is None:
        raise HTTPException(status_code=404, detail="Titre introuvable")
    as_of = latest_as_of(db)
    items = [] if as_of is None else list(db.scalars(
        select(Forecast).where(Forecast.security_id == security_id, Forecast.as_of == as_of)))
    return SecurityForecastOut(as_of=as_of, signals=_signals(_signals_of(items)),
                               horizons=_no_horizons() | {f.horizon: _horizon(f) for f in items})
