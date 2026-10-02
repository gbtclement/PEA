from datetime import date

from app.services.durations import EARLIEST, date_before, months_before


def test_months_before_clamps_day_and_floor():
    assert months_before(date(2026, 3, 31), 1) == date(2026, 2, 28)
    assert months_before(date(2024, 3, 31), 1) == date(2024, 2, 29)
    assert months_before(date(2026, 1, 15), 1) == date(2025, 12, 15)
    assert months_before(date(2026, 9, 25), 36500) == EARLIEST


def test_date_before_units():
    day = date(2026, 9, 25)
    assert date_before(day, 3, "days") == date(2026, 9, 22)
    assert date_before(day, 2, "weeks") == date(2026, 9, 11)
    assert date_before(day, 6, "months") == date(2026, 3, 25)
    assert date_before(date(2024, 2, 29), 1, "years") == date(2023, 2, 28)
    assert date_before(day, 36500, "weeks") == EARLIEST
