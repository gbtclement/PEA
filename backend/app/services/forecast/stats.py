"""Statistiques historiques : ce qui a suivi chaque signal, pour chaque horizon."""
import math
from collections import defaultdict
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

HORIZONS: dict[str, int] = {"1d": 1, "1w": 5, "1m": 21}  # en séances
BASELINE = "__all__"  # référence : toutes les actions liquides, n'importe quel jour


@dataclass
class SignalStat:
    signal: str
    horizon: str
    n: int
    mean: float
    median: float
    hit_rate: float        # part des cas en hausse
    mean_excess: float     # écart moyen avec le CAC 40 sur la même période
    beat_index: float      # part des cas au-dessus du CAC 40
    hit_after_fees: float  # part des cas qui gagnent plus que les frais aller-retour
    std_excess: float
    reliability: str
    t_stat: float

    def to_dict(self) -> dict:
        return asdict(self)


def forward_returns(close: pd.Series, h: int) -> pd.Series:
    """Rendement entre la clôture du jour et celle `h` séances plus tard (NaN en fin de série)."""
    return close.shift(-h) / close - 1


def _t_stat(mean_excess: float, std_excess: float, n: int, h: int) -> float:
    # Sur plusieurs séances, les fenêtres de cas voisins se chevauchent : ~n/h cas réellement indépendants.
    n_eff = n / h
    if std_excess <= 0 or n_eff <= 1:
        return 0.0
    return mean_excess / (std_excess / math.sqrt(n_eff))


def reliability(mean_excess: float, std_excess: float, n: int, h: int) -> str:
    t = abs(_t_stat(mean_excess, std_excess, n, h))
    if t >= 3 and n >= 200:
        return "elevee"
    if t >= 2 and n >= 100:
        return "moyenne"
    return "faible"


class StatsAccumulator:
    def __init__(self, cost: float):
        self.cost = cost
        self._returns: dict[tuple[str, str], list[np.ndarray]] = defaultdict(list)
        self._excess: dict[tuple[str, str], list[np.ndarray]] = defaultdict(list)

    def add(self, signal: str, horizon: str, returns: np.ndarray, excess: np.ndarray) -> None:
        if len(returns):
            self._returns[(signal, horizon)].append(np.asarray(returns, dtype=float))
            self._excess[(signal, horizon)].append(np.asarray(excess, dtype=float))

    def result(self) -> list[SignalStat]:
        # La fiabilité mesure l'écart avec l'action moyenne (la référence), pas avec le CAC 40 : si toutes les actions
        # ont battu l'indice sur la période, un signal qui fait pareil n'apporte aucune information.
        base_excess = {h: float(np.concatenate(self._excess[(s, h)]).mean()) for (s, h) in self._excess if s == BASELINE}
        out = []
        for (signal, horizon), chunks in self._returns.items():
            r = np.concatenate(chunks)
            x = np.concatenate(self._excess[(signal, horizon)])
            h = HORIZONS.get(horizon, 1)
            mean_x = float(x.mean())
            std_x = float(x.std(ddof=1)) if len(x) > 1 else 0.0
            relative = mean_x - (0.0 if signal == BASELINE else base_excess.get(horizon, 0.0))
            out.append(SignalStat(
                signal=signal, horizon=horizon, n=len(r), mean=float(r.mean()), median=float(np.median(r)),
                hit_rate=float((r > 0).mean()), mean_excess=mean_x, beat_index=float((x > 0).mean()),
                hit_after_fees=float((r > self.cost).mean()), std_excess=std_x,
                reliability=reliability(relative, std_x, len(r), h), t_stat=_t_stat(relative, std_x, len(r), h),
            ))
        return out
