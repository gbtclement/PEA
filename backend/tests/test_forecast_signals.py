import numpy as np
import pandas as pd
import pytest

from app.services.forecast.signals import SIGNALS, compute_signals


def series(values, volume=1_000.0):
    index = pd.bdate_range("2021-01-04", periods=len(values))
    close = pd.Series(np.asarray(values, dtype=float), index=index)
    vol = pd.Series(volume if np.ndim(volume) else [volume] * len(values), index=index, dtype=float)
    return close, vol


def test_every_signal_has_a_french_label_and_direction():
    assert len(SIGNALS) == 14
    for info in SIGNALS.values():
        assert info.label and info.description
    assert sum(info.bullish for info in SIGNALS.values()) == 8


def test_columns_are_the_signal_keys():
    close, volume = series([100.0] * 60)
    assert list(compute_signals(close, volume).columns) == list(SIGNALS)


def test_breakout_needs_a_new_20_day_high_and_volume():
    values = [100.0] * 40 + [104.0]
    close, _ = series(values)
    high_volume = pd.Series([1_000.0] * 40 + [3_000.0], index=close.index)
    normal_volume = pd.Series([1_000.0] * 41, index=close.index)
    assert compute_signals(close, high_volume)["breakout_20"].iloc[-1]
    assert not compute_signals(close, normal_volume)["breakout_20"].iloc[-1]
    assert not compute_signals(close, high_volume)["breakout_20"].iloc[:-1].any()


def test_breakdown_needs_a_new_20_day_low_and_volume():
    close, _ = series([100.0] * 40 + [96.0])
    volume = pd.Series([1_000.0] * 40 + [3_000.0], index=close.index)
    assert compute_signals(close, volume)["breakdown_20"].iloc[-1]


def test_oversold_in_an_uptrend():
    rise = list(np.linspace(50, 150, 260))
    drop = [150 * (0.98 ** i) for i in range(1, 9)]  # -15 % en 8 séances, encore au-dessus de la MM200
    close, volume = series(rise + drop)
    signals = compute_signals(close, volume)
    assert signals["oversold_uptrend"].iloc[-1]
    assert not signals["oversold_uptrend"].iloc[:260].any()


def test_golden_cross_lasts_five_sessions():
    down = list(np.linspace(200, 100, 250))
    up = list(np.linspace(101, 260, 120))
    close, volume = series(down + up)
    signals = compute_signals(close, volume)
    sma50, sma200 = close.rolling(50).mean(), close.rolling(200).mean()
    cross = int(np.argmax(((sma50 > sma200) & (sma50.shift() <= sma200.shift())).to_numpy()))
    assert cross > 250
    assert signals["golden_cross"].iloc[cross:cross + 5].all()
    assert not signals["golden_cross"].iloc[cross + 5]
    assert not signals["golden_cross"].iloc[:cross].any()


def test_signals_needing_long_windows_stay_false_on_short_history():
    close, volume = series(list(np.linspace(10, 40, 150)))  # forte hausse, mais < 200 et < 252 séances
    signals = compute_signals(close, volume)
    for key in ("trend_strong", "high_52w", "golden_cross", "oversold_uptrend", "death_cross", "trend_weak"):
        assert not signals[key].any(), key


def test_high_52w_and_strong_trend_on_long_rise():
    close, volume = series(list(np.linspace(50, 150, 300)))
    last = compute_signals(close, volume).iloc[-1]
    assert last["high_52w"] and last["trend_strong"]
    assert not last["trend_weak"]


def test_weekly_moves():
    close, volume = series([100.0] * 30 + [95, 92, 90, 89, 88])
    assert compute_signals(close, volume)["drop_week"].iloc[-1]
    close, volume = series([100.0] * 30 + [104, 108, 111, 114, 116])
    assert compute_signals(close, volume)["surge_week"].iloc[-1]


def test_volume_surge_up():
    close, _ = series([100.0] * 30 + [105.0])
    volume = pd.Series([1_000.0] * 30 + [2_500.0], index=close.index)
    assert compute_signals(close, volume)["volume_surge_up"].iloc[-1]


def test_overbought_after_a_steady_climb():
    close, volume = series([100 * (1.01 ** i) for i in range(60)])
    assert compute_signals(close, volume)["overbought"].iloc[-1]


def test_no_look_ahead():
    rng = np.random.default_rng(7)
    values = 100 * np.cumprod(1 + rng.normal(0.0005, 0.02, 600))
    volume = rng.uniform(500, 3_000, 600)
    close, vol = series(values, volume)
    full = compute_signals(close, vol)
    for n in (260, 300, 450):
        pd.testing.assert_frame_equal(compute_signals(close.iloc[:n], vol.iloc[:n]), full.iloc[:n])
    assert full.to_numpy().any()  # la série aléatoire déclenche bien des signaux


def test_missing_volume_and_short_series():
    close, _ = series(list(np.linspace(100, 90, 30)))
    volume = pd.Series(np.nan, index=close.index)
    signals = compute_signals(close, volume)
    assert signals.dtypes.eq(bool).all()
    assert not signals[["breakout_20", "breakdown_20", "volume_surge_up"]].to_numpy().any()


@pytest.mark.parametrize("key", list(SIGNALS))
def test_all_boolean_without_nan(key):
    rng = np.random.default_rng(1)
    close, volume = series(100 * np.cumprod(1 + rng.normal(0, 0.02, 400)), rng.uniform(100, 1_000, 400))
    column = compute_signals(close, volume)[key]
    assert column.dtype == bool
