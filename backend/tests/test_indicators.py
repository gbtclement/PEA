import pytest

from app.services.indicators import ema, macd, performance, rsi, sma


def test_sma():
    assert sma([1, 2, 3, 4, 5], 3) == [None, None, 2, 3, 4]
    assert sma([1, 2], 3) == [None, None]


def test_ema_seeded_with_sma():
    assert ema([1, 2, 3, 4, 5], 3) == [None, None, 2, 3, 4]


def test_rsi_all_gains():
    values = [float(i) for i in range(20)]
    assert rsi(values)[-1] == 100.0
    assert rsi(values)[13] is None


def test_rsi_balanced():
    values = [float(i % 2) for i in range(15)]  # +1, -1 alternés
    assert rsi(values)[14] == pytest.approx(50.0)


def test_rsi_constant_series():
    assert rsi([10.0] * 20)[-1] == 50.0


def test_macd_alignment_and_flat_series():
    result = macd([10.0] * 40)
    assert result.macd[24] is None and result.macd[25] == pytest.approx(0.0)
    assert result.signal[32] is None and result.signal[33] == pytest.approx(0.0)
    assert result.histogram[-1] == pytest.approx(0.0)
    assert len(result.macd) == len(result.signal) == len(result.histogram) == 40


def test_macd_rising_series_is_positive():
    result = macd([float(i) for i in range(60)])
    assert result.macd[-1] > 0


def test_performance():
    assert performance([100.0, 105.0, 110.0], 2) == pytest.approx(10.0)
    assert performance([100.0], 1) is None


def test_performance_zero_base():
    assert performance([0.0, 5.0], 1) is None
