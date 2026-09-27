"""Calcul complet : statistiques sur tout l'historique et test honnête sur l'année écoulée.

Test sur l'année écoulée (« walk-forward ») : les statistiques d'entraînement n'utilisent que des cas dont
la fenêtre se termine avant la date de coupure. Chaque jour après cette date, on prédit avec ces seules
statistiques, on retient les 10 meilleures prédictions de hausse, puis on regarde ce qui s'est vraiment passé.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from app.services.forecast.predict import Prediction, predict
from app.services.forecast.signals import SIGNALS, compute_signals
from app.services.forecast.stats import BASELINE, HORIZONS, SignalStat, StatsAccumulator, forward_returns

MAX_ABS_RETURN = 1.0   # au-delà de ±100 %, presque toujours une erreur de données (division d'action…)
TEST_SESSIONS = 252    # un an de séances pour le test
TOP_PICKS = 10
_KEYS = list(SIGNALS)


@dataclass
class SeriesInput:
    security_id: int
    close: pd.Series   # indexé par dates (Timestamp), ordre croissant
    volume: pd.Series


@dataclass(frozen=True)
class BacktestRecord:
    day: date
    security_id: int
    horizon: str
    signals: tuple[str, ...]
    actual_return: float
    actual_excess: float


@dataclass
class BacktestResult:
    days: int
    picks: int
    hit_rate: float
    hit_after_fees: float
    mean_return: float
    mean_after_fees: float
    mean_excess: float
    baseline_mean: float
    edge: float  # gain moyen des choix − gain moyen de toutes les actions les mêmes jours

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class Analysis:
    stats: list[SignalStat]
    train_stats: list[SignalStat]
    backtest: dict[str, BacktestResult]
    cutoff: date | None
    data_until: date | None
    latest: dict[int, tuple[date, list[str]]] = field(default_factory=dict)


def _liquid(series: SeriesInput, min_turnover: float) -> pd.Series:
    turnover = (series.close * series.volume).rolling(20).mean()
    return turnover >= min_turnover  # moyenne inconnue (début d'historique, volumes absents) → non liquide


def active_signals(series: SeriesInput, min_turnover: float) -> tuple[date, list[str]] | None:
    """Signaux de la dernière séance d'un titre liquide ce jour-là."""
    if len(series.close) < 2 or not bool(_liquid(series, min_turnover).iloc[-1]):
        return None
    last = compute_signals(series.close, series.volume).iloc[-1]
    return series.close.index[-1].date(), [key for key in _KEYS if last[key]]


def _index_returns(index_close: pd.Series, dates: pd.DatetimeIndex, h: int) -> np.ndarray:
    aligned = index_close.reindex(index_close.index.union(dates)).ffill().reindex(dates)
    returns = (aligned.shift(-h) / aligned - 1).to_numpy()
    return np.nan_to_num(returns, nan=0.0)


def run_analysis(series: list[SeriesInput], index_close: pd.Series, min_turnover: float, cost: float,
                 cutoff: date | None = None) -> Analysis:
    if cutoff is None and len(index_close) > TEST_SESSIONS:
        cutoff = index_close.index[-TEST_SESSIONS].date()
    cutoff_ts = pd.Timestamp(cutoff) if cutoff else None
    everything, train = StatsAccumulator(cost), StatsAccumulator(cost)
    records: list[BacktestRecord] = []
    baseline_sums: dict[tuple[str, date], list[float]] = defaultdict(lambda: [0.0, 0])
    latest: dict[int, tuple[date, list[str]]] = {}

    for s in series:
        if len(s.close) < 30:
            continue
        signals = compute_signals(s.close, s.volume)
        flags = signals.to_numpy()
        liquid = _liquid(s, min_turnover).to_numpy()
        dates = s.close.index
        if liquid[-1]:
            latest[s.security_id] = (dates[-1].date(), [k for k, on in zip(_KEYS, flags[-1]) if on])
        for horizon, h in HORIZONS.items():
            r = forward_returns(s.close, h).to_numpy()
            x = r - _index_returns(index_close, dates, h)
            valid = liquid & ~np.isnan(r) & (np.abs(r) <= MAX_ABS_RETURN)
            ends = dates[np.minimum(np.arange(len(dates)) + h, len(dates) - 1)]
            in_train = valid & (np.arange(len(dates)) + h < len(dates)) & (ends < cutoff_ts) if cutoff_ts else valid
            _accumulate(everything, horizon, flags, r, x, valid)
            _accumulate(train, horizon, flags, r, x, in_train)
            if cutoff_ts is None:
                continue
            in_test = valid & (dates >= cutoff_ts)
            for i in np.flatnonzero(in_test):
                day = dates[i].date()
                total = baseline_sums[(horizon, day)]
                total[0] += r[i]
                total[1] += 1
                if flags[i].any():
                    active = tuple(k for k, on in zip(_KEYS, flags[i]) if on)
                    records.append(BacktestRecord(day, s.security_id, horizon, active, float(r[i]), float(x[i])))

    train_stats = train.result()
    baseline = {key: total / count for key, (total, count) in baseline_sums.items() if count}
    result = backtest(records, {(t.signal, t.horizon): t for t in train_stats}, baseline, cost) if cutoff_ts else {}
    data_until = index_close.index[-1].date() if len(index_close) else None
    return Analysis(everything.result(), train_stats, result, cutoff, data_until, latest)


def _accumulate(acc: StatsAccumulator, horizon: str, flags: np.ndarray, r: np.ndarray, x: np.ndarray, mask: np.ndarray) -> None:
    acc.add(BASELINE, horizon, r[mask], x[mask])
    for j, key in enumerate(_KEYS):
        m = mask & flags[:, j]
        acc.add(key, horizon, r[m], x[m])


def backtest(records: list[BacktestRecord], train_stats: dict[tuple[str, str], SignalStat],
             baseline: dict[tuple[str, date], float], cost: float) -> dict[str, BacktestResult]:
    cache: dict[tuple[tuple[str, ...], str], Prediction | None] = {}
    by_day: dict[tuple[str, date], list[tuple[float, BacktestRecord]]] = defaultdict(list)
    for rec in records:
        key = (rec.signals, rec.horizon)
        if key not in cache:
            cache[key] = predict(list(rec.signals), rec.horizon, train_stats)
        p = cache[key]
        if p is not None and p.expected_return > 0:
            by_day[(rec.horizon, rec.day)].append((p.expected_return, rec))

    out = {}
    for horizon in HORIZONS:
        picks: list[BacktestRecord] = []
        base: list[float] = []
        days = 0
        for (h, day), candidates in by_day.items():
            if h != horizon:
                continue
            chosen = [rec for _, rec in sorted(candidates, key=lambda c: -c[0])[:TOP_PICKS]]
            picks += chosen
            base += [baseline.get((horizon, day), 0.0)] * len(chosen)
            days += 1
        if not picks:
            out[horizon] = BacktestResult(0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            continue
        r = np.array([p.actual_return for p in picks])
        x = np.array([p.actual_excess for p in picks])
        baseline_mean = float(np.mean(base))
        out[horizon] = BacktestResult(
            days=days, picks=len(picks), hit_rate=float((r > 0).mean()), hit_after_fees=float((r > cost).mean()),
            mean_return=float(r.mean()), mean_after_fees=float(r.mean() - cost), mean_excess=float(x.mean()),
            baseline_mean=baseline_mean, edge=float(r.mean() - baseline_mean),
        )
    return out
