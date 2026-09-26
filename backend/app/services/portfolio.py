"""Calculs du portefeuille : fonctions pures, sans base ni réseau. Montants en euros."""

import calendar
import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class OrderLine:
    id: int
    security_id: int
    trade_date: date
    side: str  # buy | sell
    quantity: int
    unit_price: float
    fee: float


@dataclass
class Position:
    security_id: int
    quantity: int = 0
    cost: float = 0.0  # prix de revient total des titres encore détenus, frais d'achat inclus
    realized_gain: float = 0.0

    @property
    def avg_cost(self) -> float | None:
        return self.cost / self.quantity if self.quantity else None


class OversellError(ValueError):
    def __init__(self, security_id: int, trade_date: date, held: int, requested: int) -> None:
        super().__init__(f"Vente de {requested} titres alors que {held} sont détenus au {trade_date}")
        self.security_id = security_id
        self.trade_date = trade_date
        self.held = held
        self.requested = requested


def sort_orders(orders: Iterable[OrderLine]) -> list[OrderLine]:
    """Ordre chronologique ; le même jour, les achats passent avant les ventes."""
    return sorted(orders, key=lambda o: (o.trade_date, o.side == "sell", o.id))


def _apply(positions: dict[int, Position], order: OrderLine) -> None:
    position = positions.setdefault(order.security_id, Position(order.security_id))
    if order.side == "buy":
        position.quantity += order.quantity
        position.cost += order.quantity * order.unit_price + order.fee
        return
    if order.quantity > position.quantity:
        raise OversellError(order.security_id, order.trade_date, position.quantity, order.quantity)
    sold_cost = position.cost * order.quantity / position.quantity
    position.realized_gain += order.quantity * order.unit_price - order.fee - sold_cost
    position.quantity -= order.quantity
    position.cost = position.cost - sold_cost if position.quantity else 0.0


def compute_positions(orders: Iterable[OrderLine]) -> dict[int, Position]:
    positions: dict[int, Position] = {}
    for order in sort_orders(orders):
        _apply(positions, order)
    return positions


@dataclass(frozen=True)
class OrderCounter:
    year: int
    count: int
    min_orders: int
    remaining: int
    expected_by_now: float
    behind: bool


def order_counter(dates: Iterable[date], today: date, min_orders: int) -> OrderCounter:
    """Ordres de l'année civile et rythme attendu (ordres_min × jours écoulés / jours de l'année)."""
    count = sum(1 for d in dates if d.year == today.year)
    days_in_year = 366 if calendar.isleap(today.year) else 365
    expected = min_orders * today.timetuple().tm_yday / days_in_year
    return OrderCounter(
        year=today.year, count=count, min_orders=min_orders, remaining=max(0, min_orders - count),
        expected_by_now=round(expected, 1), behind=count < min(min_orders, math.floor(expected)),
    )


@dataclass(frozen=True)
class HistoryPoint:
    day: date
    value: float
    invested: float


def value_history(
    orders: Iterable[OrderLine], closes: dict[int, list[tuple[date, float]]], rates: dict[int, float], until: date,
) -> list[HistoryPoint]:
    """Valeur du portefeuille à chaque séance depuis le premier ordre (clôtures converties en euros).

    Sans clôture connue pour un titre, sa valeur est son prix de revient.
    """
    ordered = sort_orders(orders)
    if not ordered:
        return []
    start = ordered[0].trade_date
    days = sorted({d for series in closes.values() for d, _ in series if start <= d <= until})
    positions: dict[int, Position] = {}
    last_close: dict[int, float] = {}
    cursors = {sid: 0 for sid in closes}
    next_order = 0
    points: list[HistoryPoint] = []
    for day in days:
        while next_order < len(ordered) and ordered[next_order].trade_date <= day:
            _apply(positions, ordered[next_order])
            next_order += 1
        for sid, series in closes.items():
            while cursors[sid] < len(series) and series[cursors[sid]][0] <= day:
                last_close[sid] = series[cursors[sid]][1]
                cursors[sid] += 1
        value = sum(
            p.quantity * last_close[sid] * rates.get(sid, 1.0) if sid in last_close else p.cost
            for sid, p in positions.items() if p.quantity
        )
        invested = sum(p.cost for p in positions.values())
        points.append(HistoryPoint(day, round(value, 2), round(invested, 2)))
    return points
