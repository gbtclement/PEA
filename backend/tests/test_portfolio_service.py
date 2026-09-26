from datetime import date

import pytest

from app.services.portfolio import OrderLine, OversellError, compute_positions, order_counter, value_history


def line(id_, side, qty, price, fee=0.0, day=date(2026, 1, 5), sid=1):
    return OrderLine(id=id_, security_id=sid, trade_date=day, side=side, quantity=qty, unit_price=price, fee=fee)


def test_average_cost_includes_buy_fees():
    positions = compute_positions([line(1, "buy", 10, 50, 2.4), line(2, "buy", 10, 60, 2.88, day=date(2026, 2, 1))])
    p = positions[1]
    assert p.quantity == 20
    assert p.cost == pytest.approx(1105.28)
    assert p.avg_cost == pytest.approx(55.264)


def test_sale_keeps_average_cost_and_books_realized_gain():
    p = compute_positions([line(1, "buy", 10, 50, 5), line(2, "sell", 4, 70, 1, day=date(2026, 3, 1))])[1]
    assert p.quantity == 6
    assert p.avg_cost == pytest.approx(50.5)
    assert p.realized_gain == pytest.approx(4 * 70 - 1 - 4 * 50.5)


def test_full_sale_then_rebuy_resets_cost():
    p = compute_positions([
        line(1, "buy", 10, 50, 5), line(2, "sell", 10, 60, 3, day=date(2026, 2, 1)),
        line(3, "buy", 5, 80, 2, day=date(2026, 3, 1)),
    ])[1]
    assert p.quantity == 5
    assert p.avg_cost == pytest.approx(80.4)
    assert p.realized_gain == pytest.approx(600 - 3 - 505)


def test_oversell_raises_with_details():
    with pytest.raises(OversellError) as error:
        compute_positions([line(1, "buy", 3, 50), line(2, "sell", 5, 60, day=date(2026, 2, 1))])
    assert (error.value.held, error.value.requested, error.value.trade_date) == (3, 5, date(2026, 2, 1))


def test_sell_before_buy_in_time_is_oversell_even_if_entered_later():
    with pytest.raises(OversellError):
        compute_positions([line(2, "buy", 5, 50, day=date(2026, 3, 1)), line(1, "sell", 5, 60, day=date(2026, 2, 1))])


def test_same_day_buy_then_sell_is_allowed():
    p = compute_positions([line(2, "sell", 5, 60), line(1, "buy", 5, 50)])[1]
    assert p.quantity == 0 and p.avg_cost is None


def test_order_counter_on_pace_and_behind():
    dates = [date(2026, m, 1) for m in range(1, 9)] + [date(2025, 12, 31)]
    counter = order_counter(dates, today=date(2026, 9, 26), min_orders=12)
    assert (counter.year, counter.count, counter.remaining) == (2026, 8, 4)
    assert counter.expected_by_now == pytest.approx(8.8)
    assert counter.behind is False
    assert order_counter(dates[:5], today=date(2026, 9, 26), min_orders=12).behind is True


def test_order_counter_goal_reached_and_zero_goal():
    counter = order_counter([date(2026, 1, 2)] * 14, today=date(2026, 3, 1), min_orders=12)
    assert (counter.remaining, counter.behind) == (0, False)
    assert order_counter([], today=date(2026, 3, 1), min_orders=0).behind is False


def test_value_history_rebuilds_daily_value():
    orders = [line(1, "buy", 10, 10, 1, day=date(2026, 1, 5)), line(2, "buy", 5, 20, 0, day=date(2026, 1, 7), sid=2)]
    closes = {1: [(date(2026, 1, 2), 9.0), (date(2026, 1, 5), 10.0), (date(2026, 1, 6), 11.0), (date(2026, 1, 7), 12.0)],
              2: [(date(2026, 1, 7), 21.0)]}
    points = value_history(orders, closes, rates={1: 1.0, 2: 0.5}, until=date(2026, 1, 7))
    assert [(p.day, p.value, p.invested) for p in points] == [
        (date(2026, 1, 5), 100.0, 101.0), (date(2026, 1, 6), 110.0, 101.0), (date(2026, 1, 7), 172.5, 201.0)]


def test_value_history_empty_and_missing_close_uses_cost():
    assert value_history([], {}, {}, until=date(2026, 1, 7)) == []
    points = value_history([line(1, "buy", 2, 10, 0, day=date(2026, 1, 5), sid=1), line(2, "buy", 1, 30, 0, day=date(2026, 1, 5), sid=2)],
                           {1: [(date(2026, 1, 5), 12.0)]}, {1: 1.0, 2: 1.0}, until=date(2026, 1, 5))
    assert [(p.value, p.invested) for p in points] == [(54.0, 50.0)]
