"""Prévisions court terme : statistiques des signaux (chaque semaine) et prédictions du jour (chaque matin)."""
from datetime import date, timedelta

import pandas as pd

from app.jobs.context import JobContext
from app.models import ForecastRun
from app.repositories.forecasts import (
    closes_between, index_closes, latest_run, pending_forecasts, replace_forecasts, stock_currencies, stock_series,
)
from app.services.fees import DEFAULT_GRID_JSON, broker_fee, grid_from_json
from app.services.forecast.engine import SeriesInput, active_signals, run_analysis
from app.services.forecast.predict import predict
from app.services.forecast.stats import HORIZONS, SignalStat
from app.services.fx import to_eur
from app.services.market_calendar import PARIS, last_session_close

REFERENCE_ORDER_EUR = 500.0
STATS_MAX_AGE = timedelta(days=7)
RECENT_WINDOW = timedelta(days=420)  # ≈ 290 séances : assez pour la moyenne 200 jours et le plus haut sur 1 an
# Les statistiques des signaux gardent 5 ans (+ marge) : elles ne lisent pas tout l'historique.
STATS_WINDOW = timedelta(days=365 * 5 + 30)


def _inputs(frames, currencies: dict[int, str]) -> list[SeriesInput]:
    # Actions cotées hors euro (couronnes, dollars…) : sans conversion, leur liquidité serait faussée
    return [
        SeriesInput(sid, f["close"], f["volume"], eur_rate=to_eur(1.0, currencies.get(sid)))
        for sid, f in frames.items() if len(f)
    ]


def _closed_until(ctx: JobContext) -> date:
    """Dernière séance clôturée : une barre du jour prise en pleine séance n'est pas encore un cours de clôture."""
    return last_session_close(ctx.now()).astimezone(PARIS).date()


def refresh_forecast_stats(ctx: JobContext) -> int:
    today = ctx.now().astimezone(PARIS).date()
    since = today - STATS_WINDOW
    with ctx.session_factory() as session:
        # Prévisions communes à tous les comptes : coût d'un aller-retour avec la grille standard.
        _, rate = broker_fee(REFERENCE_ORDER_EUR, grid_from_json(DEFAULT_GRID_JSON))
        cost = 2 * rate
        closed = pd.Timestamp(_closed_until(ctx))
        frames = {sid: f.loc[:closed] for sid, f in stock_series(session, since, include_inactive=True).items()}
        series = _inputs(frames, stock_currencies(session))
        index = index_closes(session, since).loc[:closed]
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
    closed = _closed_until(ctx)
    with ctx.session_factory() as session:
        run = latest_run(session)
        stats = {(s["signal"], s["horizon"]): SignalStat(**s) for s in run.stats}
        frames = {sid: f.loc[: pd.Timestamp(closed)] for sid, f in stock_series(session, closed - RECENT_WINDOW).items()}
        frames = {sid: f for sid, f in frames.items() if len(f)}
        as_of = max((f.index[-1].date() for f in frames.values()), default=None)
        rows: list[dict] = []
        for s in _inputs(frames, stock_currencies(session)):
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
        written = replace_forecasts(session, as_of, rows) if as_of else 0
        resolved = _resolve(session, closed)
        session.commit()
        return written + resolved


def _resolve(session, closed: date) -> int:
    """Vérifie les prédictions dont l'horizon (en séances du titre) est atteint, séances clôturées seulement.

    Départ et arrivée sont relus dans l'historique stocké : après une division d'action, tout l'historique est
    rechargé à la nouvelle échelle et le rapport reste juste.
    """
    pending = pending_forecasts(session)
    if not pending:
        return 0
    start = min(f.as_of for items in pending.values() for f in items)
    closes = closes_between(session, list(pending), start, closed)
    resolved = 0
    for security_id, items in pending.items():
        history = closes.get(security_id, [])
        by_day = dict(history)
        for f in items:
            later = [(day, close) for day, close in history if day > f.as_of]
            h = HORIZONS[f.horizon]
            if len(later) >= h:
                day, close = later[h - 1]
                f.actual_return = close / by_day.get(f.as_of, f.base_close) - 1
                f.resolved_on = day
                resolved += 1
    return resolved
