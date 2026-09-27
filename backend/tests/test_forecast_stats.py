import math

import numpy as np
import pandas as pd
import pytest

from app.services.forecast.predict import predict
from app.services.forecast.stats import BASELINE, HORIZONS, SignalStat, StatsAccumulator, forward_returns, reliability


def test_horizons():
    assert HORIZONS == {"1d": 1, "1w": 5, "1m": 21}


def test_forward_returns():
    close = pd.Series([100.0, 110.0, 121.0])
    result = forward_returns(close, 1)
    assert result.iloc[:2].tolist() == pytest.approx([0.1, 0.1])
    assert math.isnan(result.iloc[2])
    assert forward_returns(close, 2).iloc[0] == pytest.approx(0.21)


def test_accumulator_aggregates_per_signal_and_horizon():
    acc = StatsAccumulator(cost=0.01)
    acc.add("breakout_20", "1w", np.array([0.05, -0.02, 0.005, 0.03]), np.array([0.02, -0.03, -0.01, 0.01]))
    acc.add("breakout_20", "1w", np.array([0.00]), np.array([0.001]))
    [stat] = acc.result()
    assert (stat.signal, stat.horizon, stat.n) == ("breakout_20", "1w", 5)
    assert stat.mean == pytest.approx(0.013)
    assert stat.median == pytest.approx(0.005)
    assert stat.hit_rate == pytest.approx(3 / 5)  # 0,05 ; 0,005 ; 0,03
    assert stat.hit_after_fees == pytest.approx(2 / 5)  # > 1 % de frais : 0,05 et 0,03
    assert stat.beat_index == pytest.approx(3 / 5)
    assert stat.mean_excess == pytest.approx(np.mean([0.02, -0.03, -0.01, 0.01, 0.001]))
    assert set(stat.to_dict()) >= {"signal", "horizon", "n", "mean", "hit_rate", "reliability", "t_stat"}


def test_accumulator_ignores_empty_keys():
    acc = StatsAccumulator(cost=0.0)
    acc.add("x", "1d", np.array([]), np.array([]))
    assert acc.result() == []


@pytest.mark.parametrize(("mean", "std", "n", "h", "expected"), [
    (0.01, 0.05, 5_000, 1, "elevee"),   # t = 14
    (-0.01, 0.05, 5_000, 1, "elevee"),  # un signal baissier fiable est aussi « élevé »
    (0.002, 0.05, 1_000, 1, "faible"),  # t ≈ 1,3
    (0.004, 0.05, 1_000, 1, "moyenne"),  # t ≈ 2,5
    (0.01, 0.05, 50, 1, "faible"),      # trop peu de cas
    (0.01, 0.05, 1_000, 21, "faible"),   # fenêtres qui se chevauchent : n_eff ≈ 48, t ≈ 1,4
])
def test_reliability(mean, std, n, h, expected):
    assert reliability(mean, std, n, h) == expected


def stat(signal, horizon, n, mean, hit, mean_excess=None, std=0.05):
    mean_excess = mean if mean_excess is None else mean_excess
    t = mean_excess / (std / math.sqrt(n / HORIZONS[horizon]))
    return SignalStat(signal, horizon, n, mean, mean, hit, mean_excess, 0.5, hit, std, reliability(mean_excess, std, n, HORIZONS[horizon]), t)


@pytest.fixture
def stats():
    items = [
        stat(BASELINE, "1w", 1_000_000, 0.002, 0.52, mean_excess=0.0),
        stat("breakout_20", "1w", 5_000, 0.012, 0.58),
        stat("trend_strong", "1w", 20_000, 0.006, 0.55),
        stat("rare", "1w", 10, 0.20, 0.90),
        stat("breakdown_20", "1w", 4_000, -0.010, 0.44),
    ]
    return {(s.signal, s.horizon): s for s in items}


def test_single_signal_prediction_is_shrunk_towards_baseline(stats):
    p = predict(["breakout_20"], "1w", stats)
    assert 0.002 < p.expected_return < 0.012
    assert p.expected_return == pytest.approx(0.002 + 1000 / 1050 * 0.010)  # n_eff = 1000, poids 1000/(1000+50)
    assert 0.52 < p.prob_up < 0.58
    assert p.signals == ["breakout_20"]
    assert p.reliability == stats[("breakout_20", "1w")].reliability


def test_rare_signal_barely_moves_the_prediction(stats):
    p = predict(["rare"], "1w", stats)
    assert p.expected_return < 0.002 + 0.2 * 0.05  # n_eff = 2 → poids 2/52
    assert p.reliability == "faible"


def test_two_signals_are_averaged_by_number_of_cases(stats):
    p = predict(["breakout_20", "trend_strong"], "1w", stats)
    only_trend = predict(["trend_strong"], "1w", stats)
    only_breakout = predict(["breakout_20"], "1w", stats)
    assert only_trend.expected_return < p.expected_return < only_breakout.expected_return
    assert p.expected_return < (only_trend.expected_return + only_breakout.expected_return) / 2  # trend a 4× plus de cas


def test_bearish_signal_gives_negative_expectation(stats):
    assert predict(["breakdown_20"], "1w", stats).expected_return < 0


def test_no_signal_or_unknown_signal_gives_none(stats):
    assert predict([], "1w", stats) is None
    assert predict(["unknown"], "1w", stats) is None
    assert predict(["breakout_20"], "1d", stats) is None  # pas de statistiques pour cet horizon
