"""Alertes de prix (N2) : création, réarmement. Pas de commit ici."""
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DailyPrice, PriceAlert, Security, SecurityQuote
from app.services.fx import currency_for_market
from app.services.notifications.prefs import recipients
from app.services.notifications.send import notify

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


def check_price_alerts(db: Session, now: datetime) -> int:
    """N2 : chaque alerte active dont le seuil est franchi part une fois, puis se désactive (pas de commit)."""
    enabled: dict = {user.id: user for user, _ in recipients(db, "price_alert")}
    rows = db.execute(
        select(PriceAlert, SecurityQuote.price, Security)
        .join(SecurityQuote, SecurityQuote.security_id == PriceAlert.security_id)
        .join(Security, Security.id == PriceAlert.security_id)
        .where(PriceAlert.active.is_(True))
        .with_for_update(of=PriceAlert, skip_locked=True)
    ).all()
    sent = 0
    for alert, price, security in rows:
        user = enabled.get(alert.user_id)
        if user is None or not reached(alert.direction, alert.price, price):
            continue
        alert.active, alert.triggered_at = False, now
        notify(db, user, "price_alert",
               {"security_id": security.id, "name": security.name, "direction": alert.direction, "target": alert.price,
                "price": price, "currency": currency_for_market(security.market)},
               dedupe_key=f"price_alert:{alert.id}:{int(now.timestamp())}")
        sent += 1
    db.flush()
    return sent
