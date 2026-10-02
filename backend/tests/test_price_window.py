from datetime import date, timedelta

from app.services.price_window import choose_interval, groups

MONDAY = date(2026, 9, 21)


def test_choose_interval():
    assert choose_interval(date(2016, 9, 25), date(2026, 9, 25), 2500) == "day"
    assert choose_interval(date(2016, 9, 25), date(2026, 9, 25), 2501) == "week"   # 10 ans
    assert choose_interval(date(2010, 1, 4), date(2026, 9, 25), 4200) == "month"   # au-delà de 10 ans


def test_groups_by_week_and_month():
    days = [MONDAY + timedelta(days=i) for i in range(10)]  # lundi 21/09 → mercredi 30/09
    assert groups(days, "day") == [[i] for i in range(10)]
    assert groups(days, "week") == [list(range(7)), [7, 8, 9]]
    assert groups(days, "month") == [list(range(10))]
    assert groups([date(2026, 9, 30), date(2026, 10, 1)], "month") == [[0], [1]]
