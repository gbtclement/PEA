"""Alertes de prix (N2) : création, réarmement. Pas de commit ici."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DailyPrice, PriceAlert, SecurityQuote

MAX_ACTIVE = 50


class AlertRefused(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def reached(direction: str, target: float, price: float) -> bool:
    return price >= target if direction == "above" else price <= target


def current_price(db: Session, security_id: int) -> float | None:
    """Dernier cours connu, dans la devise du titre."""
    quote = db.get(SecurityQuote, security_id)
    if quote is not None:
        return quote.price
    return db.scalars(select(DailyPrice.close).where(DailyPrice.security_id == security_id)
                      .order_by(DailyPrice.date.desc()).limit(1)).first()


def check_new_threshold(db: Session, user_id: uuid.UUID, security_id: int, direction: str, price: float,
                        *, ignore: uuid.UUID | None = None) -> None:
    """Refuse une 51e alerte active, ou un seuil déjà franchi (elle partirait tout de suite)."""
    active = select(func.count()).select_from(PriceAlert).where(PriceAlert.user_id == user_id, PriceAlert.active.is_(True))
    if ignore is not None:
        active = active.where(PriceAlert.id != ignore)
    if db.scalar(active) >= MAX_ACTIVE:
        raise AlertRefused(400, "alert_limit", f"{MAX_ACTIVE} alertes actives au plus : supprimez-en une.")
    now_price = current_price(db, security_id)
    if now_price is not None and reached(direction, price, now_price):
        side = "au-dessus" if direction == "above" else "en dessous"
        raise AlertRefused(400, "already_reached", f"Le cours est déjà {side} de ce prix : choisissez un autre seuil.")
