"""Prédiction d'une action à partir des statistiques de ses signaux actifs."""
from dataclasses import dataclass

from app.services.forecast.stats import BASELINE, HORIZONS, SignalStat

SHRINK = 50  # un signal avec peu de cas indépendants est ramené vers la moyenne générale


@dataclass
class Prediction:
    expected_return: float
    prob_up: float
    reliability: str
    signals: list[str]


def predict(active: list[str], horizon: str, stats: dict[tuple[str, str], SignalStat]) -> Prediction | None:
    base = stats.get((BASELINE, horizon))
    known = [stats[(s, horizon)] for s in active if (s, horizon) in stats]
    if base is None or not known:
        return None
    h = HORIZONS[horizon]
    total = sum(s.n / h for s in known)
    expected = base.mean
    prob = base.hit_rate
    for s in known:
        n_eff = s.n / h
        weight = n_eff / (n_eff + SHRINK)
        expected += weight * n_eff * (s.mean - base.mean) / total
        prob += weight * n_eff * (s.hit_rate - base.hit_rate) / total
    strongest = max(known, key=lambda s: abs(s.t_stat))
    return Prediction(expected, min(max(prob, 0.0), 1.0), strongest.reliability, [s.signal for s in known])
