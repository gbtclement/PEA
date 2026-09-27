from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.services.forecast.engine import BacktestRecord, SeriesInput, active_signals, backtest, run_analysis
from app.services.forecast.stats import BASELINE, SignalStat

DATES = pd.bdate_range("2021-01-04", periods=400)


def make_series(security_id, values, volume=100_000.0):
    close = pd.Series(np.asarray(values, dtype=float), index=DATES[: len(values)])
    vol = pd.Series(volume, index=close.index, dtype=float)
    return SeriesInput(security_id, close, vol)


def random_walk(seed, n=400):
    rng = np.random.default_rng(seed)
    return 50 * np.cumprod(1 + rng.normal(0.0003, 0.02, n))


INDEX = pd.Series(100 * np.cumprod(1 + np.full(400, 0.0002)), index=DATES)


def by_key(stats):
    return {(s.signal, s.horizon): s for s in stats}


def test_only_liquid_days_count():
    liquid = make_series(1, random_walk(1))
    illiquid = make_series(2, random_walk(2), volume=10.0)  # ~500 € échangés par jour
    alone = by_key(run_analysis([liquid], INDEX, min_turnover=500_000, cost=0.01).stats)
    both = by_key(run_analysis([liquid, illiquid], INDEX, min_turnover=500_000, cost=0.01).stats)
    assert both[(BASELINE, "1d")].n == alone[(BASELINE, "1d")].n > 0


def test_outliers_are_excluded():
    values = random_walk(3)
    clean = by_key(run_analysis([make_series(1, values)], INDEX, 0, 0.01).stats)[(BASELINE, "1d")]
    glitch = values.copy()
    glitch[200:] *= 3  # division d'action mal corrigée : +200 % en une séance
    dirty = by_key(run_analysis([make_series(1, glitch)], INDEX, 0, 0.01).stats)[(BASELINE, "1d")]
    assert dirty.n == clean.n - 1
    assert dirty.mean == pytest.approx(clean.mean, abs=0.002)


def test_excess_is_measured_against_the_index():
    values = 50 * np.cumprod(np.full(400, 1.001))
    stat = by_key(run_analysis([make_series(1, values)], INDEX, 0, 0.0).stats)[(BASELINE, "1d")]
    assert stat.mean == pytest.approx(0.001)
    assert stat.mean_excess == pytest.approx(0.001 - 0.0002, abs=1e-6)


def test_training_stats_stop_before_the_cutoff():
    series = [make_series(i, random_walk(i)) for i in range(4)]
    cutoff = DATES[300].date()
    analysis = run_analysis(series, INDEX, 0, 0.01, cutoff=cutoff)
    all_n = by_key(analysis.stats)[(BASELINE, "1w")].n
    train_n = by_key(analysis.train_stats)[(BASELINE, "1w")].n
    # Liquidité connue à partir de la 20e séance (t ≥ 19). Entraînement : fenêtres terminées avant la coupure
    # (t + 5 < 300, donc t ≤ 294) → 276 séances par titre ; en tout : t ≤ 394 → 376.
    assert train_n == 4 * 276
    assert all_n == 4 * 376
    assert analysis.cutoff == cutoff
    assert set(analysis.backtest) == {"1d", "1w", "1m"}


def test_default_cutoff_is_one_year_before_the_end():
    analysis = run_analysis([make_series(1, random_walk(1))], INDEX, 0, 0.01)
    assert analysis.cutoff == DATES[-252].date()


def test_no_backtest_on_short_history():
    short_index = INDEX.iloc[:200]
    analysis = run_analysis([make_series(1, random_walk(1, 200))], short_index, 0, 0.01)
    assert analysis.cutoff is None
    assert analysis.backtest == {}


def _stat(signal, mean, hit, n=10_000):
    return SignalStat(signal, "1w", n, mean, mean, hit, mean, 0.5, hit, 0.05, "elevee", 5.0)


def test_backtest_uses_only_the_training_statistics():
    train = {(s.signal, "1w"): s for s in [
        _stat(BASELINE, 0.002, 0.52), _stat("drop_week", -0.02, 0.40), _stat("breakout_20", 0.01, 0.58),
    ]}
    day = date(2022, 3, 1)
    records = [
        # drop_week a rapporté +30 % pendant l'année de test, mais l'entraînement le dit baissier : jamais choisi
        BacktestRecord(day, 1, "1w", ("drop_week",), 0.30, 0.29),
        BacktestRecord(day, 2, "1w", ("breakout_20",), 0.02, 0.015),
    ]
    baseline = {("1w", day): 0.004}
    result = backtest(records, train, baseline, cost=0.01)["1w"]
    assert result.picks == 1
    assert result.mean_return == pytest.approx(0.02)
    assert result.mean_after_fees == pytest.approx(0.01)
    assert result.hit_rate == 1.0
    assert result.baseline_mean == pytest.approx(0.004)
    assert result.edge == pytest.approx(0.016)
    assert result.days == 1


def test_backtest_keeps_the_ten_best_per_day():
    train = {(s.signal, "1w"): s for s in [_stat(BASELINE, 0.0, 0.5)] + [_stat(f"s{i}", 0.001 * i, 0.5) for i in range(1, 16)]}
    day = date(2022, 3, 1)
    records = [BacktestRecord(day, i, "1w", (f"s{i}",), 0.01 * i, 0.0) for i in range(1, 16)]
    result = backtest(records, train, {("1w", day): 0.0}, cost=0.0)["1w"]
    assert result.picks == 10
    assert result.mean_return == pytest.approx(np.mean([0.01 * i for i in range(6, 16)]))


def test_active_signals_on_the_last_session():
    rng = np.random.default_rng(5)
    values = 50 * np.cumprod(1 + rng.normal(0, 0.02, 300))
    values[-5:] = values[-6] * np.array([0.97, 0.95, 0.93, 0.90, 0.88])  # −12 % sur la semaine
    series = make_series(1, values)
    last_day, active = active_signals(series, min_turnover=0)
    assert last_day == DATES[299].date()
    assert "drop_week" in active
    assert active_signals(make_series(2, values, volume=1.0), min_turnover=500_000) is None
