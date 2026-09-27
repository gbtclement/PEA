"""Signaux techniques quotidiens, calculés uniquement avec les données disponibles le jour même.

Chaque signal est vrai ou faux pour chaque séance. Un indicateur dont la fenêtre n'est pas encore
complète (par exemple la moyenne 200 jours sur un titre récent) donne toujours « faux ».
"""
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class SignalInfo:
    label: str
    description: str
    bullish: bool  # intuition courante ; les statistiques disent ce qui s'est vraiment passé


SIGNALS: dict[str, SignalInfo] = {
    "breakout_20": SignalInfo("Cassure du plus haut 20 jours", "Le cours dépasse son plus haut des 20 dernières séances, avec des volumes 1,5 fois supérieurs à la moyenne.", True),
    "trend_strong": SignalInfo("Tendance haussière forte", "Cours au-dessus de la moyenne 50 jours, elle-même au-dessus de la moyenne 200 jours, et plus de +10 % en 3 mois.", True),
    "oversold_uptrend": SignalInfo("Survente en tendance haussière", "RSI sous 30 (forte baisse récente) alors que le cours reste au-dessus de sa moyenne 200 jours.", True),
    "golden_cross": SignalInfo("Croisement doré", "La moyenne 50 jours vient de passer au-dessus de la moyenne 200 jours (5 dernières séances).", True),
    "macd_cross_up": SignalInfo("MACD haussier", "Le MACD passe au-dessus de sa ligne de signal aujourd'hui.", True),
    "drop_week": SignalInfo("Forte baisse sur 1 semaine", "Au moins −10 % sur les 5 dernières séances : un rebond est parfois observé.", True),
    "high_52w": SignalInfo("Plus haut sur 1 an", "Le cours atteint son plus haut des 12 derniers mois.", True),
    "volume_surge_up": SignalInfo("Hausse sur gros volumes", "Au moins +4 % aujourd'hui avec des volumes 2 fois supérieurs à la moyenne.", True),
    "breakdown_20": SignalInfo("Cassure du plus bas 20 jours", "Le cours passe sous son plus bas des 20 dernières séances, avec des volumes 1,5 fois supérieurs à la moyenne.", False),
    "trend_weak": SignalInfo("Tendance baissière forte", "Cours sous la moyenne 50 jours, elle-même sous la moyenne 200 jours, et plus de −10 % en 3 mois.", False),
    "overbought": SignalInfo("Surachat", "RSI au-dessus de 75 : le cours a beaucoup monté en peu de temps.", False),
    "death_cross": SignalInfo("Croisement de la mort", "La moyenne 50 jours vient de passer sous la moyenne 200 jours (5 dernières séances).", False),
    "macd_cross_down": SignalInfo("MACD baissier", "Le MACD passe sous sa ligne de signal aujourd'hui.", False),
    "surge_week": SignalInfo("Forte hausse sur 1 semaine", "Au moins +15 % sur les 5 dernières séances : un repli est parfois observé.", False),
}

_MACD_WARMUP = 35  # 26 séances pour la moyenne lente + 9 pour la ligne de signal


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rsi = 100 - 100 / (1 + gain / loss)
    rsi = rsi.mask((loss == 0) & (gain > 0), 100.0)
    return rsi.mask((loss == 0) & (gain == 0), 50.0)


def _crosses_above(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a > b) & (a.shift() <= b.shift())


def _within(flags: pd.Series, sessions: int) -> pd.Series:
    return flags.astype(float).rolling(sessions, min_periods=1).max() > 0


def compute_signals(close: pd.Series, volume: pd.Series) -> pd.DataFrame:
    """Une colonne booléenne par signal (ordre de `SIGNALS`), indexée comme `close`."""
    close = close.astype(float)
    volume = volume.reindex(close.index).astype(float)
    sma50, sma200 = close.rolling(50).mean(), close.rolling(200).mean()
    perf_3m = close / close.shift(63) - 1
    perf_week = close / close.shift(5) - 1
    day = close.pct_change(fill_method=None)
    rsi = _rsi(close)
    avg_volume = volume.shift(1).rolling(20).mean()  # moyenne des 20 séances précédentes
    prev_high, prev_low = close.shift(1).rolling(20).max(), close.shift(1).rolling(20).min()
    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    macd_ready = pd.Series(range(len(close)), index=close.index) >= _MACD_WARMUP

    columns = {
        "breakout_20": (close > prev_high) & (volume > 1.5 * avg_volume),
        "trend_strong": (close > sma50) & (sma50 > sma200) & (perf_3m > 0.10),
        "oversold_uptrend": (rsi < 30) & (close > sma200),
        "golden_cross": _within(_crosses_above(sma50, sma200), 5),
        "macd_cross_up": _crosses_above(macd, macd_signal) & macd_ready,
        "drop_week": perf_week <= -0.10,
        "high_52w": close >= close.rolling(252).max(),
        "volume_surge_up": (day >= 0.04) & (volume >= 2 * avg_volume),
        "breakdown_20": (close < prev_low) & (volume > 1.5 * avg_volume),
        "trend_weak": (close < sma50) & (sma50 < sma200) & (perf_3m < -0.10),
        "overbought": rsi > 75,
        "death_cross": _within(_crosses_above(sma200, sma50), 5),
        "macd_cross_down": _crosses_above(macd_signal, macd) & macd_ready,
        "surge_week": perf_week >= 0.15,
    }
    return pd.DataFrame({key: columns[key].fillna(False).astype(bool) for key in SIGNALS}, index=close.index)
