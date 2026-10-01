"""N1 : forte variation d'un favori ou d'une position, au plus une fois par titre et par jour. Pas de commit ici."""
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Favorite, MoveNotice, Security, SecurityQuote
from app.repositories.orders import order_lines
from app.services.fx import currency_for_market
from app.services.market_calendar import PARIS
from app.services.notifications.prefs import recipients
from app.services.notifications.send import notify
from app.services.portfolio import compute_positions


def followed_ids(db: Session, user_id: uuid.UUID) -> set[int]:
    favorites = set(db.scalars(select(Favorite.security_id).where(Favorite.user_id == user_id)))
    held = {sid for sid, p in compute_positions(order_lines(db, user_id)).items() if p.quantity}
    return favorites | held


def notify_price_moves(db: Session, now: datetime) -> int:
    today = now.astimezone(PARIS).date()
    sent = 0
    for user, prefs in recipients(db, "price_move"):
        already = set(db.scalars(select(MoveNotice.security_id).where(MoveNotice.user_id == user.id,
                                                                      MoveNotice.day == today)))
        ids = followed_ids(db, user.id) - already
        if not ids:
            continue
        rows = db.execute(
            select(Security, SecurityQuote).join(SecurityQuote, SecurityQuote.security_id == Security.id)
            .where(Security.id.in_(ids), SecurityQuote.change_pct.is_not(None),
                   func.abs(SecurityQuote.change_pct) >= prefs.move_threshold_pct)
        ).all()
        moves = [(s, q) for s, q in rows if q.as_of.astimezone(PARIS).date() == today]  # cours du jour seulement
        if not moves:
            continue
        items = sorted(({"security_id": s.id, "name": s.name, "change_pct": q.change_pct, "price": q.price,
                         "currency": currency_for_market(s.market)} for s, q in moves),
                       key=lambda item: -abs(item["change_pct"]))
        notify(db, user, "price_move", {"threshold": prefs.move_threshold_pct, "items": items},
               dedupe_key=f"price_move:{user.id}:{now.astimezone(PARIS):%Y%m%d%H%M}")
        db.add_all(MoveNotice(user_id=user.id, security_id=s.id, day=today) for s, _ in moves)
        db.flush()
        sent += 1
    return sent
