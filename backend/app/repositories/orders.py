from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import DailyPrice, Order, Security
from app.services.portfolio import OrderLine


def list_orders(session: Session, user_id: int) -> list[tuple[Order, Security]]:
    stmt = (select(Order, Security).join(Security, Security.id == Order.security_id)
            .where(Order.user_id == user_id).order_by(Order.trade_date.desc(), Order.id.desc()))
    return [(o, s) for o, s in session.execute(stmt)]


def to_line(order: Order) -> OrderLine:
    return OrderLine(id=order.id, security_id=order.security_id, trade_date=order.trade_date, side=order.side,
                     quantity=order.quantity, unit_price=order.unit_price, fee=order.fee)


def order_lines(session: Session, user_id: int) -> list[OrderLine]:
    return [to_line(o) for o in session.scalars(select(Order).where(Order.user_id == user_id))]


def held_security_ids(session: Session) -> set[int]:
    """Titres détenus par au moins un utilisateur (quantité nette positive)."""
    signed = func.sum(case((Order.side == "buy", Order.quantity), else_=-Order.quantity))
    return set(session.scalars(select(Order.security_id).group_by(Order.security_id).having(signed > 0)))


def closes_since(session: Session, ids: set[int], since: date) -> dict[int, list[tuple[date, float]]]:
    result: dict[int, list[tuple[date, float]]] = {sid: [] for sid in ids}
    if not ids:
        return result
    stmt = (select(DailyPrice.security_id, DailyPrice.date, DailyPrice.close)
            .where(DailyPrice.security_id.in_(ids), DailyPrice.date >= since).order_by(DailyPrice.date))
    for sid, day, close in session.execute(stmt):
        result[sid].append((day, close))
    return result
