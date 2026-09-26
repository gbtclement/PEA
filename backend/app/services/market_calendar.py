from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
OPEN = time(9, 0)
CLOSE = time(17, 35)
EARLY_CLOSE = time(14, 5)


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


def is_trading_day(day: date) -> bool:
    return day.weekday() < 5 and day not in euronext_holidays(day.year)


def is_market_open(now: datetime) -> bool:
    local = now.astimezone(PARIS)
    if not is_trading_day(local.date()):
        return False
    close = EARLY_CLOSE if (local.month, local.day) in ((12, 24), (12, 31)) else CLOSE
    return OPEN <= local.time() < close
