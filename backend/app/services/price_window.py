"""Regroupement des barres journalières du graphique d'une fiche (semaine ou mois au-delà de ~2 500 points)."""
from datetime import date, timedelta
from typing import Literal

Interval = Literal["day", "week", "month"]

MAX_DAILY_POINTS = 2500  # au-delà, le graphique devient lent
WEEKLY_MAX_SPAN = timedelta(days=3660)  # jusqu'à 10 ans (et quelques jours) : une barre par semaine, sinon par mois


def choose_interval(first: date, last: date, count: int) -> Interval:
    if count <= MAX_DAILY_POINTS:
        return "day"
    return "week" if last - first <= WEEKLY_MAX_SPAN else "month"


def _key(day: date, interval: Interval) -> date:
    if interval == "week":
        return day - timedelta(days=day.weekday())
    if interval == "month":
        return day.replace(day=1)
    return day


def groups(days: list[date], interval: Interval) -> list[list[int]]:
    """Positions des jours (triés) regroupées par semaine ou par mois ; une position par groupe en journalier."""
    result: list[list[int]] = []
    previous: date | None = None
    for position, day in enumerate(days):
        key = _key(day, interval)
        if key != previous:
            result.append([])
            previous = key
        result[-1].append(position)
    return result
