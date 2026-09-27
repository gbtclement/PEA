from datetime import UTC, date, datetime

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import func, select

from app.jobs.forecasts import refresh_forecast_stats, refresh_forecasts
from app.models import DailyPrice, Forecast, ForecastRun
from tests.factories import make_security

NOW = datetime(2026, 9, 28, 5, 0, tzinfo=UTC)  # lundi 7 h à Paris, avant l'ouverture
DAYS = pd.bdate_range(end="2026-09-25", periods=320)


def add_prices(db, security, closes, volumes=None, days=DAYS):
    volumes = volumes if volumes is not None else [50_000] * len(closes)
    for day, close, volume in zip(days, closes, volumes):
        db.add(DailyPrice(security_id=security.id, date=day.date(), open=close, high=close, low=close, close=float(close), volume=int(volume)))
    db.flush()


@pytest.fixture
def market(db):
    """Un indice, une action en forte hausse (signaux haussiers le dernier jour) et deux actions au hasard."""
    index = make_security(db, "^FCHI", kind="index", name="CAC 40")
    add_prices(db, index, 7000 * np.cumprod(np.full(320, 1.0003)))
    rising = make_security(db, "UP.PA", name="Montée")
    add_prices(db, rising, np.linspace(20, 60, 320))
    others = []
    for seed in (1, 2):
        s = make_security(db, f"R{seed}.PA", name=f"Hasard {seed}")
        rng = np.random.default_rng(seed)
        add_prices(db, s, 30 * np.cumprod(1 + rng.normal(0.0005, 0.02, 320)))
        others.append(s)
    return {"index": index, "rising": rising, "others": others}


def test_stats_run_is_stored_with_the_default_round_trip_cost(db, make_ctx, market):
    count = refresh_forecast_stats(make_ctx(now=NOW, min_turnover_eur=0))
    run = db.scalars(select(ForecastRun)).one()
    assert count == len(run.stats) > 0
    assert run.round_trip_cost == pytest.approx(0.0096)  # 2 × 0,48 % pour un ordre de 500 €
    assert run.data_until == date(2026, 9, 25)
    assert run.cutoff == DAYS[-252].date()
    assert set(run.backtest) == {"1d", "1w", "1m"}
    assert any(s["signal"] == "__all__" and s["horizon"] == "1w" for s in run.stats)
    assert all(s["signal"] != "__all__" or s["n"] > 0 for s in run.stats)


def test_daily_forecasts_are_ranked_and_not_duplicated(db, make_ctx, market):
    ctx = make_ctx(now=NOW, min_turnover_eur=0)
    refresh_forecasts(ctx)  # aucun calcul encore : les statistiques sont calculées d'abord
    assert db.scalar(select(func.count()).select_from(ForecastRun)) == 1
    rows = db.scalars(select(Forecast).where(Forecast.security_id == market["rising"].id)).all()
    assert {r.horizon for r in rows} == {"1d", "1w", "1m"}
    rising = next(r for r in rows if r.horizon == "1w")
    assert rising.as_of == date(2026, 9, 25)
    assert rising.base_close == pytest.approx(60.0)
    assert "trend_strong" in rising.signals and "high_52w" in rising.signals
    assert rising.actual_return is None
    for horizon in ("1d", "1w", "1m"):
        ranks = sorted(db.scalars(select(Forecast.rank).where(Forecast.horizon == horizon)))
        assert ranks == list(range(1, len(ranks) + 1))
    before = db.scalar(select(func.count()).select_from(Forecast))
    refresh_forecasts(ctx)
    assert db.scalar(select(func.count()).select_from(Forecast)) == before


def test_forecasts_are_checked_once_the_horizon_is_reached(db, make_ctx, market):
    ctx = make_ctx(now=NOW, min_turnover_eur=0)
    refresh_forecasts(ctx)
    later = pd.bdate_range(start="2026-09-28", periods=5)
    add_prices(db, market["rising"], [60, 61, 62, 63, 66], days=later)
    refresh_forecasts(make_ctx(now=datetime(2026, 10, 5, 5, 0, tzinfo=UTC), min_turnover_eur=0))
    first = {f.horizon: f for f in db.scalars(select(Forecast).where(
        Forecast.security_id == market["rising"].id, Forecast.as_of == date(2026, 9, 25)))}
    assert first["1d"].actual_return == pytest.approx(0.0)
    assert first["1d"].resolved_on == date(2026, 9, 28)
    assert first["1w"].actual_return == pytest.approx(0.10)
    assert first["1w"].resolved_on == date(2026, 10, 2)
    assert first["1m"].actual_return is None
    newer = db.scalars(select(Forecast).where(Forecast.as_of == date(2026, 10, 2))).all()
    assert {f.security_id for f in newer} == {market["rising"].id}  # les autres titres n'ont pas de cours plus récent


def test_illiquid_stocks_get_no_forecast(db, make_ctx, market):
    refresh_forecasts(make_ctx(now=NOW, min_turnover_eur=10_000_000))  # plus aucun titre assez échangé
    assert db.scalar(select(func.count()).select_from(Forecast)) == 0
