"""Prévisions court terme : statistiques des signaux (chaque semaine) et prédictions du jour (chaque matin)."""
from datetime import timedelta

from app.core.current_user import ensure_default_user
from app.jobs.context import JobContext
from app.models import ForecastRun
from app.repositories.forecasts import (
    closes_after, index_closes, latest_run, pending_forecasts, stock_series, upsert_forecasts,
)
from app.repositories.user_settings import user_fee_grid
from app.services.fees import broker_fee
from app.services.forecast.engine import SeriesInput, active_signals, run_analysis
from app.services.forecast.predict import predict
from app.services.forecast.stats import HORIZONS, SignalStat
from app.services.market_calendar import PARIS

REFERENCE_ORDER_EUR = 500.0
STATS_MAX_AGE = timedelta(days=7)
RECENT_WINDOW = timedelta(days=420)  # ≈ 290 séances : assez pour la moyenne 200 jours et le plus haut sur 1 an


def _inputs(frames) -> list[SeriesInput]:
    return [SeriesInput(sid, f["close"], f["volume"]) for sid, f in frames.items()]


def refresh_forecast_stats(ctx: JobContext) -> int:
    today = ctx.now().astimezone(PARIS).date()
    since = today - timedelta(days=365 * ctx.settings.history_years + 30)
    with ctx.session_factory() as session:
        user = ensure_default_user(session)
        _, rate = broker_fee(REFERENCE_ORDER_EUR, user_fee_grid(session, user.id))
        cost = 2 * rate
        series = _inputs(stock_series(session, since))
        index = index_closes(session, since)
        analysis = run_analysis(series, index, ctx.settings.min_turnover_eur, cost)
        session.add(ForecastRun(
            computed_at=ctx.now(), data_until=analysis.data_until, cutoff=analysis.cutoff, round_trip_cost=cost,
            stats=[s.to_dict() for s in analysis.stats],
            backtest={h: r.to_dict() for h, r in analysis.backtest.items()},
        ))
        session.commit()
        return len(analysis.stats)


def stats_are_stale(ctx: JobContext) -> bool:
    with ctx.session_factory() as session:
        run = latest_run(session)
        return run is None or run.computed_at < ctx.now() - STATS_MAX_AGE


def refresh_forecasts(ctx: JobContext) -> int:
    """Enregistre les prédictions de la dernière séance, puis vérifie celles dont l'horizon est atteint."""
    with ctx.session_factory() as session:
        missing = latest_run(session) is None
    if missing:
        refresh_forecast_stats(ctx)
    today = ctx.now().astimezone(PARIS).date()
    with ctx.session_factory() as session:
        run = latest_run(session)
        stats = {(s["signal"], s["horizon"]): SignalStat(**s) for s in run.stats}
        frames = stock_series(session, today - RECENT_WINDOW)
        as_of = max((f.index[-1].date() for f in frames.values()), default=None)
        rows: list[dict] = []
        for s in _inputs(frames):
            found = active_signals(s, ctx.settings.min_turnover_eur)
            if not found or found[0] != as_of or not found[1]:
                continue
            for horizon in HORIZONS:
                p = predict(found[1], horizon, stats)
                if p is not None:
                    rows.append(dict(security_id=s.security_id, as_of=as_of, horizon=horizon,
                                     expected_return=p.expected_return, prob_up=p.prob_up, reliability=p.reliability,
                                     signals=p.signals, base_close=float(s.close.iloc[-1]), rank=0))
        for horizon in HORIZONS:
            ranked = sorted((r for r in rows if r["horizon"] == horizon), key=lambda r: -r["expected_return"])
            for position, row in enumerate(ranked, start=1):
                row["rank"] = position
        written = upsert_forecasts(session, rows)
        resolved = _resolve(session)
        session.commit()
        return written + resolved


def _resolve(session) -> int:
    resolved = 0
    for security_id, pending in pending_forecasts(session).items():
        closes = closes_after(session, security_id, min(f.as_of for f in pending))
        for f in pending:
            later = [(day, close) for day, close in closes if day > f.as_of]
            h = HORIZONS[f.horizon]
            if len(later) >= h:
                day, close = later[h - 1]
                f.actual_return = close / f.base_close - 1
                f.resolved_on = day
                resolved += 1
    return resolved
