from datetime import UTC, date, datetime

import pytest

from app.services.market_calendar import easter_sunday, euronext_holidays, is_market_open, is_trading_day


@pytest.mark.parametrize("year, expected", [(2026, date(2026, 4, 5)), (2027, date(2027, 3, 28)), (2025, date(2025, 4, 20))])
def test_easter_sunday(year, expected):
    assert easter_sunday(year) == expected


def test_holidays_2026():
    assert euronext_holidays(2026) == {
        date(2026, 1, 1), date(2026, 4, 3), date(2026, 4, 6), date(2026, 5, 1), date(2026, 12, 25), date(2026, 12, 26),
    }


def test_trading_days():
    assert is_trading_day(date(2026, 9, 28))       # lundi
    assert not is_trading_day(date(2026, 9, 26))   # samedi
    assert not is_trading_day(date(2026, 4, 3))    # Vendredi saint


@pytest.mark.parametrize("utc_dt, expected", [
    (datetime(2026, 9, 28, 7, 30, tzinfo=UTC), True),    # 9h30 à Paris (UTC+2)
    (datetime(2026, 9, 28, 6, 59, tzinfo=UTC), False),   # 8h59
    (datetime(2026, 9, 28, 15, 34, tzinfo=UTC), True),   # 17h34
    (datetime(2026, 9, 28, 15, 35, tzinfo=UTC), False),  # 17h35 : fermé
    (datetime(2026, 12, 7, 8, 0, tzinfo=UTC), True),     # 9h00 à Paris l'hiver (UTC+1)
    (datetime(2026, 12, 24, 12, 0, tzinfo=UTC), True),   # 13h00, clôture anticipée à 14h05
    (datetime(2026, 12, 24, 13, 10, tzinfo=UTC), False), # 14h10
    (datetime(2026, 4, 3, 8, 0, tzinfo=UTC), False),     # Vendredi saint
    (datetime(2026, 9, 26, 10, 0, tzinfo=UTC), False),   # samedi
])
def test_is_market_open(utc_dt, expected):
    assert is_market_open(utc_dt) is expected
