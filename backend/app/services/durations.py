"""Durées libres du simulateur : « il y a 2 semaines », « il y a 10 ans »."""
from calendar import monthrange
from datetime import date, timedelta
from typing import Literal

Unit = Literal["days", "weeks", "months", "years"]

EARLIEST = date(1900, 1, 1)  # plancher : aucune cotation n'est plus ancienne, et on reste dans le calendrier


def months_before(day: date, months: int) -> date:
    """Même jour, `months` mois plus tôt ; ramené au dernier jour du mois s'il n'existe pas (31/03 → 28/02)."""
    year, month = divmod(day.year * 12 + day.month - 1 - months, 12)
    if year < EARLIEST.year:
        return EARLIEST
    return date(year, month + 1, min(day.day, monthrange(year, month + 1)[1]))


def date_before(day: date, duration: int, unit: Unit) -> date:
    if unit == "days":
        return max(EARLIEST, day - timedelta(days=duration))
    if unit == "weeks":
        return max(EARLIEST, day - timedelta(weeks=duration))
    return months_before(day, duration * 12 if unit == "years" else duration)
