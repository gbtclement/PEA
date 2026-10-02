from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
NEW_YORK = ZoneInfo("America/New_York")
OPEN = time(9, 0)
CLOSE = time(17, 35)
EARLY_CLOSE = time(14, 5)
US_MARKETS = frozenset({"NYSE", "NYSE American", "NYSE Arca", "Nasdaq"})


def easter_sunday(year: int) -> date:
    """Algorithme grégorien anonyme (Meeus/Jones/Butcher)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def euronext_holidays(year: int) -> set[date]:
    easter = easter_sunday(year)
    return {
        date(year, 1, 1),
        easter - timedelta(days=2),
        easter + timedelta(days=1),
        date(year, 5, 1),
        date(year, 12, 25),
        date(year, 12, 26),
    }


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_monday_of_may(year: int) -> date:
    last = date(year, 5, 31)
    return last - timedelta(days=last.weekday())


def _observed(day: date) -> date:
    """Férié tombant un samedi : chômé le vendredi ; un dimanche : le lundi."""
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def us_holidays(year: int) -> set[date]:
    days = {
        _nth_weekday(year, 1, 0, 3),  # Martin Luther King
        _nth_weekday(year, 2, 0, 3),  # Presidents' Day
        easter_sunday(year) - timedelta(days=2),  # Vendredi saint
        _last_monday_of_may(year),  # Memorial Day
        _nth_weekday(year, 9, 0, 1),  # Labor Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving
    }
    days |= {_observed(date(year, month, day)) for month, day in ((6, 19), (7, 4), (12, 25))}
    new_year = date(year, 1, 1)
    if new_year.weekday() != 5:  # un 1er janvier un samedi n'est pas reporté au 31 décembre
        days.add(_observed(new_year))
    return days


def us_early_closes(year: int) -> set[date]:
    days = {_nth_weekday(year, 11, 3, 4) + timedelta(days=1)}
    holidays = us_holidays(year)
    days |= {d for d in (date(year, 7, 3), date(year, 12, 24)) if d.weekday() < 5 and d not in holidays}
    return days


@dataclass(frozen=True)
class Calendar:
    code: str
    label: str
    tz: ZoneInfo
    open: time
    close: time
    early_close: time
    holidays: Callable[[int], set[date]]
    early_closes: Callable[[int], set[date]]

    def is_trading_day(self, day: date) -> bool:
        return day.weekday() < 5 and day not in self.holidays(day.year)

    def close_time(self, day: date) -> time:
        return self.early_close if day in self.early_closes(day.year) else self.close

    def session_close(self, day: date) -> datetime:
        return datetime.combine(day, self.close_time(day), tzinfo=self.tz)

    def is_open(self, now: datetime) -> bool:
        local = now.astimezone(self.tz)
        return self.is_trading_day(local.date()) and self.open <= local.time() < self.close_time(local.date())

    def last_session_close(self, now: datetime) -> datetime:
        """Heure de clôture de la dernière séance terminée à l'instant `now`."""
        day = now.astimezone(self.tz).date()
        while True:
            if self.is_trading_day(day) and self.session_close(day) <= now:
                return self.session_close(day)
            day -= timedelta(days=1)


EUROPE = Calendar("europe", "Europe", PARIS, OPEN, CLOSE, EARLY_CLOSE, euronext_holidays,
                  lambda year: {date(year, 12, 24), date(year, 12, 31)})
US = Calendar("us", "New York", NEW_YORK, time(9, 30), time(16, 0), time(13, 0), us_holidays, us_early_closes)
CALENDARS = (EUROPE, US)


def calendar_for_market(market: str) -> Calendar:
    return US if market in US_MARKETS else EUROPE


def open_calendars(now: datetime) -> list[Calendar]:
    return [calendar for calendar in CALENDARS if calendar.is_open(now)]


def any_market_open(now: datetime) -> bool:
    return bool(open_calendars(now))


# Fonctions historiques : elles parlent de la séance européenne (Paris).
def is_trading_day(day: date) -> bool:
    return EUROPE.is_trading_day(day)


def is_market_open(now: datetime) -> bool:
    return EUROPE.is_open(now)


def last_session_close(now: datetime) -> datetime:
    return EUROPE.last_session_close(now)
