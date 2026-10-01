"""Valeur du portefeuille d'un membre au dernier cours connu : page Portefeuille et récaps par mail."""
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyPrice, Security, SecurityQuote
from app.repositories.orders import order_lines
from app.services.fx import currency_for_market, to_eur
from app.services.portfolio import Position, compute_positions


def eur_rate(security: Security) -> float:
    return to_eur(1.0, currency_for_market(security.market)) or 1.0


def last_close(db: Session, security_id: int) -> float | None:
    return db.scalars(select(DailyPrice.close).where(DailyPrice.security_id == security_id)
                      .order_by(DailyPrice.date.desc()).limit(1)).first()


@dataclass
class ValuedPosition:
    position: Position
    security: Security
    quote: SecurityQuote | None
    price: float | None  # en euros
    value: float


@dataclass
class PortfolioValue:
    positions: list[ValuedPosition]
    total: float
    invested: float
    day_change: float
    realized: float

    @property
    def day_change_pct(self) -> float | None:
        base = self.total - self.day_change
        return round(self.day_change / base * 100, 2) if base else None


def value_portfolio(db: Session, user_id: uuid.UUID, today: date) -> PortfolioValue:
    lines = order_lines(db, user_id)
    positions = compute_positions(lines)
    bought_today: dict[int, tuple[int, float]] = {}  # titres achetés aujourd'hui : (quantité, montant)
    for line in lines:
        if line.side == "buy" and line.trade_date == today:
            qty, amount = bought_today.get(line.security_id, (0, 0.0))
            bought_today[line.security_id] = (qty + line.quantity, amount + line.quantity * line.unit_price)
    open_positions = [p for p in positions.values() if p.quantity]
    valued: list[ValuedPosition] = []
    day_change = 0.0
    for p in open_positions:
        security = db.get(Security, p.security_id)
        quote = db.get(SecurityQuote, p.security_id)
        rate = eur_rate(security)
        native = quote.price if quote else last_close(db, p.security_id)
        price = round(native * rate, 4) if native is not None else None
        value = round(p.quantity * price, 2) if price is not None else round(p.cost, 2)
        if quote and quote.previous_close:
            # Les titres achetés aujourd'hui varient depuis leur prix d'achat, pas depuis la clôture de la veille.
            today_qty, today_amount = bought_today.get(p.security_id, (0, 0.0))
            kept_today = min(today_qty, p.quantity)
            average_buy = today_amount / today_qty if today_qty else 0.0
            day_change += (p.quantity - kept_today) * (quote.price - quote.previous_close) * rate
            day_change += kept_today * (quote.price * rate - average_buy)
        valued.append(ValuedPosition(position=p, security=security, quote=quote, price=price, value=value))
    return PortfolioValue(
        positions=valued, total=round(sum(v.value for v in valued), 2),
        invested=round(sum(p.cost for p in open_positions), 2), day_change=round(day_change, 2),
        realized=round(sum(p.realized_gain for p in positions.values()), 2),
    )
