import pytest

from app.services.scoring.components import (
    dividend, growth, macd_component, momentum, rsi_component, solidity, trend, valuation,
)
from app.services.scoring.score import ScoreInputs, compute_score


def test_trend():
    assert trend(110, 100, 90).points == 20
    assert trend(95, 100, 90).points == 7 + 6
    assert trend(80, 100, 110).points == 0
    assert trend(80, None, 110) is None
    assert trend(110, 100, 90).message.startswith("✅")


@pytest.mark.parametrize("diff, expected", [(-15, 0), (-10, 0), (0, 7.5), (10, 15), (20, 15)])
def test_momentum(diff, expected):
    assert momentum(5 + diff, 5).points == pytest.approx(expected)


def test_momentum_missing_index():
    assert momentum(5, None) is None


@pytest.mark.parametrize("value, expected", [(50, 10), (40, 10), (60, 10), (35, 6), (65, 6), (70, 6), (25, 4), (75, 0)])
def test_rsi_component(value, expected):
    assert rsi_component(value).points == expected


def test_macd_crossover_recent():
    macd_line = [-1, -1, -1, -1, -1, 1, 1]
    signal = [0, 0, 0, 0, 0, 0, 0]
    assert macd_component(macd_line, signal).points == 5


def test_macd_above_signal_without_recent_cross():
    macd_line = [1] * 10
    signal = [0] * 10
    assert macd_component(macd_line, signal).points == 3


def test_macd_below_signal():
    assert macd_component([-1] * 10, [0] * 10).points == 0


def test_macd_not_enough_data():
    assert macd_component([None, None, 1], [None, None, 0]) is None


@pytest.mark.parametrize("pe, expected", [(8, 15), (11.5, 7.5), (15, 0), (30, 0), (-5, 0)])
def test_valuation(pe, expected):
    assert valuation(pe, 10).points == pytest.approx(expected)


def test_valuation_missing():
    assert valuation(None, 10) is None
    assert valuation(12, None) is None


def test_growth_halves():
    full = growth(0.20, 0.15)
    assert (full.points, full.max_points) == (15, 15)
    half = growth(0.075, None)
    assert (half.points, half.max_points) == (pytest.approx(3.75), 7.5)
    assert growth(None, None) is None


def test_solidity():
    assert solidity(0.3, 0.12).points == 10
    assert solidity(2.5, -0.1).points == 0
    assert solidity(None, 0.05).max_points == 5


@pytest.mark.parametrize("value, expected", [(0.0, 0), (0.01, 5), (0.04, 10), (0.07, 7), (0.10, 5)])
def test_dividend(value, expected):
    assert dividend(value).points == pytest.approx(expected)


def test_dividend_missing():
    assert dividend(None) is None


PERFECT = dict(
    price=120, sma50=110, sma200=100, perf_3m=20, index_perf_3m=5, rsi=50,
    macd_line=[-1, -1, -1, -1, -1, 1, 1], signal_line=[0] * 7,
    pe=8, sector_median_pe=10, eps_growth=0.2, revenue_growth=0.2, debt_to_equity=0.2, profit_margin=0.2,
    dividend_yield=0.04,
)


def test_compute_score_perfect():
    result = compute_score(ScoreInputs(**PERFECT))
    assert result.total == 100
    assert result.technical == 100 and result.fundamental == 100
    assert result.available_ratio == 1.0
    assert len(result.components) == 8


def test_compute_score_without_fundamentals_is_normalized():
    technical_only = {k: v for k, v in PERFECT.items() if k in (
        "price", "sma50", "sma200", "perf_3m", "index_perf_3m", "rsi", "macd_line", "signal_line")}
    result = compute_score(ScoreInputs(**technical_only))
    assert result.total == 100
    assert result.fundamental is None
    assert result.available_ratio == 0.5


def test_compute_score_etf_ignores_fundamentals():
    result = compute_score(ScoreInputs(**PERFECT), kind="etf")
    assert result.available_ratio == 1.0
    assert result.fundamental is None
    assert {c.group for c in result.components} == {"technical"}


def test_compute_score_nothing_available():
    result = compute_score(ScoreInputs())
    assert result.total is None and result.available_ratio == 0.0
