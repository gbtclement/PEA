"""Composants du score : chaque fonction renvoie None quand la donnée est indisponible."""

from dataclasses import dataclass

from app.services.scoring.config import MAX_POINTS

_DEFAULT_MAX = {"trend": 20, "momentum": 15, "rsi": 10, "macd": 5, "valuation": 15, "growth": 15, "solidity": 10, "dividend": 10}


@dataclass(frozen=True)
class Component:
    key: str
    label: str
    points: float
    max_points: float
    message: str
    group: str  # technical | fundamental


def _lin(x: float, x_lo: float, x_hi: float, p_lo: float, p_hi: float) -> float:
    if x <= x_lo:
        return p_lo
    if x >= x_hi:
        return p_hi
    return p_lo + (x - x_lo) / (x_hi - x_lo) * (p_hi - p_lo)


def _fr(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def _pct(fraction: float | None) -> str:
    return "n.d." if fraction is None else f"{fraction * 100:+.0f} %".replace(".", ",")


def _make(key: str, label: str, points: float, max_points: float, message: str, group: str) -> Component:
    scale = MAX_POINTS[key] / _DEFAULT_MAX[key]
    return Component(key, label, round(points * scale, 2), round(max_points * scale, 2), message, group)


def trend(price: float | None, sma50: float | None, sma200: float | None) -> Component | None:
    if price is None or sma50 is None or sma200 is None:
        return None
    points = 7 * (price > sma50) + 7 * (price > sma200) + 6 * (sma50 > sma200)
    if points >= 14:
        message = "✅ Tendance haussière (cours au-dessus des moyennes 50 et 200 jours)"
    elif points == 0:
        message = "❌ Tendance baissière (cours sous les moyennes 50 et 200 jours)"
    else:
        message = "⚠️ Tendance mitigée"
    return _make("trend", "Tendance", points, 20, message, "technical")


def momentum(perf_3m: float | None, index_perf_3m: float | None) -> Component | None:
    if perf_3m is None or index_perf_3m is None:
        return None
    diff = perf_3m - index_perf_3m
    points = _lin(diff, -10, 10, 0, 15)
    if diff >= 0:
        message = f"✅ Fait mieux que le CAC 40 sur 3 mois ({_fr(diff)} pts)"
    else:
        message = f"⚠️ Fait moins bien que le CAC 40 sur 3 mois ({_fr(diff)} pts)"
    return _make("momentum", "Dynamique 3 mois", points, 15, message, "technical")


def rsi_component(value: float | None) -> Component | None:
    if value is None:
        return None
    shown = _fr(value, 0)
    if 40 <= value <= 60:
        points, message = 10, f"✅ RSI équilibré ({shown})"
    elif 30 <= value < 40 or 60 < value <= 70:
        points, message = 6, f"⚠️ RSI proche d'une zone extrême ({shown})"
    elif value < 30:
        points, message = 4, f"⚠️ RSI en zone de survente ({shown}) : rebond possible mais risqué"
    else:
        points, message = 0, f"❌ RSI en surchauffe ({shown})"
    return _make("rsi", "RSI 14", points, 10, message, "technical")


def macd_component(macd_line: list[float | None], signal_line: list[float | None]) -> Component | None:
    pairs = [(m, s) for m, s in zip(macd_line, signal_line) if m is not None and s is not None]
    if len(pairs) < 6:
        return None
    recent_cross = any(pairs[i][0] > pairs[i][1] and pairs[i - 1][0] <= pairs[i - 1][1] for i in range(len(pairs) - 5, len(pairs)))
    if recent_cross:
        points, message = 5, "✅ Signal MACD haussier récent"
    elif pairs[-1][0] > pairs[-1][1]:
        points, message = 3, "✅ MACD au-dessus de son signal"
    else:
        points, message = 0, "⚠️ MACD sous son signal"
    return _make("macd", "MACD", points, 5, message, "technical")


def valuation(pe: float | None, sector_median_pe: float | None) -> Component | None:
    if pe is None or sector_median_pe is None or sector_median_pe <= 0:
        return None
    if pe <= 0:
        return _make("valuation", "Valorisation", 0, 15, "❌ Entreprise en perte (PER négatif)", "fundamental")
    ratio = pe / sector_median_pe
    points = _lin(ratio, 0.8, 1.5, 15, 0)
    detail = f"PER {_fr(pe)} contre {_fr(sector_median_pe)} pour le secteur"
    message = f"✅ Valorisation attractive ({detail})" if ratio <= 1 else f"⚠️ Valorisation élevée ({detail})"
    return _make("valuation", "Valorisation", points, 15, message, "fundamental")


def growth(eps_growth: float | None, revenue_growth: float | None) -> Component | None:
    halves = [g for g in (eps_growth, revenue_growth) if g is not None]
    if not halves:
        return None
    points = sum(_lin(g, 0, 0.15, 0, 7.5) for g in halves)
    max_points = 7.5 * len(halves)
    detail = f"bénéfices {_pct(eps_growth)}, chiffre d'affaires {_pct(revenue_growth)}"
    message = f"✅ Croissance solide ({detail})" if points >= max_points / 2 else f"⚠️ Croissance faible ({detail})"
    return _make("growth", "Croissance", points, max_points, message, "fundamental")


def solidity(debt_to_equity: float | None, profit_margin: float | None) -> Component | None:
    points = max_points = 0.0
    if debt_to_equity is not None:
        points += _lin(debt_to_equity, 0.5, 2.0, 5, 0)
        max_points += 5
    if profit_margin is not None:
        points += _lin(profit_margin, 0, 0.10, 0, 5)
        max_points += 5
    if max_points == 0:
        return None
    message = "✅ Bilan solide (dette maîtrisée, bonnes marges)" if points >= max_points / 2 else "⚠️ Bilan fragile (dette élevée ou marges faibles)"
    return _make("solidity", "Solidité", points, max_points, message, "fundamental")


def dividend(dividend_yield: float | None) -> Component | None:
    if dividend_yield is None:
        return None
    shown = _fr(dividend_yield * 100)
    if dividend_yield <= 0:
        points, message = 0, "⚠️ Pas de dividende"
    elif dividend_yield < 0.02:
        points, message = _lin(dividend_yield, 0, 0.02, 0, 10), f"⚠️ Dividende modeste ({shown} %)"
    elif dividend_yield <= 0.06:
        points, message = 10, f"✅ Dividende de {shown} %"
    elif dividend_yield <= 0.08:
        points, message = 7, f"✅ Dividende élevé ({shown} %)"
    else:
        points, message = 5, f"⚠️ Rendement très élevé ({shown} %) : à vérifier"
    return _make("dividend", "Dividende", points, 10, message, "fundamental")
