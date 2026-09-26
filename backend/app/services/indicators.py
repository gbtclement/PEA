"""Indicateurs techniques calculés sur une série de clôtures (la plus ancienne en premier)."""

from dataclasses import dataclass


def sma(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    total = 0.0
    for i, value in enumerate(values):
        total += value
        if i >= window:
            total -= values[i - window]
        if i >= window - 1:
            out[i] = total / window
    return out


def ema(values: list[float], span: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < span:
        return out
    k = 2 / (span + 1)
    previous = sum(values[:span]) / span
    out[span - 1] = previous
    for i in range(span, len(values)):
        previous = values[i] * k + previous * (1 - k)
        out[i] = previous
    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    return 100 - 100 / (1 + avg_gain / avg_loss)


def rsi(values: list[float], period: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        delta = values[i] - values[i - 1]
        gains += max(delta, 0.0)
        losses += max(-delta, 0.0)
    avg_gain, avg_loss = gains / period, losses / period
    out[period] = _rsi_value(avg_gain, avg_loss)
    for i in range(period + 1, len(values)):
        delta = values[i] - values[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(delta, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-delta, 0.0)) / period
        out[i] = _rsi_value(avg_gain, avg_loss)
    return out


@dataclass(frozen=True)
class Macd:
    macd: list[float | None]
    signal: list[float | None]
    histogram: list[float | None]


def macd(values: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Macd:
    fast_ema, slow_ema = ema(values, fast), ema(values, slow)
    line = [f - s if f is not None and s is not None else None for f, s in zip(fast_ema, slow_ema)]
    signal_line: list[float | None] = [None] * len(values)
    start = next((i for i, v in enumerate(line) if v is not None), None)
    if start is not None:
        tail = ema([v for v in line[start:] if v is not None], signal)
        for offset, value in enumerate(tail):
            signal_line[start + offset] = value
    histogram = [m - s if m is not None and s is not None else None for m, s in zip(line, signal_line)]
    return Macd(line, signal_line, histogram)


def performance(values: list[float], periods: int) -> float | None:
    """Variation en % entre la valeur d'il y a `periods` séances et la dernière."""
    if len(values) <= periods:
        return None
    base = values[-1 - periods]
    if base == 0:
        return None
    return (values[-1] / base - 1) * 100
