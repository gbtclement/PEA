"""N3 récap du soir (et N4, Task 8). Pas de commit ici."""
import uuid
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Favorite, Security, SecurityQuote
from app.services.market_calendar import PARIS, is_trading_day
from app.services.notifications.prefs import recipients
from app.services.notifications.send import notify
from app.services.portfolio_value import value_portfolio


def favorite_movers(db: Session, user_id: uuid.UUID, today: date, n: int = 3) -> tuple[list[dict], list[dict]]:
    """Plus fortes hausses et baisses du jour parmi les favoris."""
    rows = db.execute(
        select(Security, SecurityQuote).join(Favorite, Favorite.security_id == Security.id)
        .join(SecurityQuote, SecurityQuote.security_id == Security.id)
        .where(Favorite.user_id == user_id, SecurityQuote.change_pct.is_not(None))
    ).all()
    items = sorted(({"security_id": s.id, "name": s.name, "change_pct": q.change_pct}
                    for s, q in rows if q.as_of.astimezone(PARIS).date() == today), key=lambda i: i["change_pct"])
    gainers = [i for i in reversed(items) if i["change_pct"] > 0][:n]
    losers = [i for i in items if i["change_pct"] < 0][:n]
    return gainers, losers


def send_daily_recaps(db: Session, now: datetime) -> int:
    today = now.astimezone(PARIS).date()
    if not is_trading_day(today):
        return 0
    sent = 0
    for user, _ in recipients(db, "daily_recap"):
        valued = value_portfolio(db, user.id, today)
        gainers, losers = favorite_movers(db, user.id, today)
        if not valued.positions and not gainers and not losers:
            continue
        if notify(db, user, "daily_recap",
                  {"day": today, "has_portfolio": bool(valued.positions), "total_value": valued.total,
                   "day_change": valued.day_change, "day_change_pct": valued.day_change_pct,
                   "gainers": gainers, "losers": losers},
                  dedupe_key=f"daily_recap:{user.id}:{today}") is not None:
            sent += 1
    return sent
