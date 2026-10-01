"""N5 : rappel du compteur d'ordres, les 1er octobre, novembre et décembre. Pas de commit ici."""
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.orders import order_lines
from app.repositories.user_settings import get_user_settings
from app.services.market_calendar import PARIS
from app.services.notifications.prefs import recipients
from app.services.notifications.send import notify
from app.services.portfolio import order_counter


def send_order_reminders(db: Session, now: datetime) -> int:
    today = now.astimezone(PARIS).date()
    sent = 0
    for user, _ in recipients(db, "order_reminder"):
        dates = [line.trade_date for line in order_lines(db, user.id)]
        if not dates:  # aucun portefeuille suivi ici (Ruling 4)
            continue
        settings = get_user_settings(db, user.id)
        counter = order_counter(dates, today, settings.min_orders_per_year)
        if counter.remaining == 0:
            continue
        if notify(db, user, "order_reminder",
                  {"year": counter.year, "count": counter.count, "min_orders": counter.min_orders,
                   "remaining": counter.remaining, "penalty_fee": settings.penalty_fee},
                  dedupe_key=f"order_reminder:{user.id}:{today:%Y-%m}") is not None:
            sent += 1
    return sent
