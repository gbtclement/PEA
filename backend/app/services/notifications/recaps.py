"""N3 récap du soir et N4 récap de la semaine. Pas de commit ici."""
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Favorite, Forecast, ScoreSnapshot, Security, SecurityQuote, SecurityScore
from app.repositories.user_envelopes import user_envelopes
from app.services.market_calendar import PARIS, is_trading_day
from app.services.notifications.prefs import recipients
from app.services.notifications.scores import previous_day, snapshot, user_top_ids
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


def _names(db: Session, ids: set[int]) -> list[dict]:
    rows = db.execute(select(Security.id, Security.name).where(Security.id.in_(ids)).order_by(Security.name)).all()
    return [{"security_id": sid, "name": name} for sid, name in rows]


def send_weekly_recaps(db: Session, now: datetime) -> int:
    """N4, le samedi : performance sur 5 séances, top 10 entrées et sorties, prévisions à une semaine vérifiées."""
    today = now.astimezone(PARIS).date()
    latest = db.scalar(select(func.max(ScoreSnapshot.day)).where(ScoreSnapshot.day <= today))
    start = previous_day(db, latest - timedelta(days=6)) if latest else None
    after = snapshot(db, latest) if latest else {}
    before = snapshot(db, start) if start else after
    checked = db.scalars(select(Forecast).where(Forecast.horizon == "1w", Forecast.rank <= 10,
                                                Forecast.actual_return.is_not(None),
                                                Forecast.resolved_on > today - timedelta(days=7))).all()
    right = sum(1 for f in checked if (f.actual_return > 0) == (f.expected_return > 0))
    sent = 0
    for user, _ in recipients(db, "weekly_recap"):
        envelopes = user_envelopes(db, user.id)  # entrées et sorties du top 10 de ce membre
        top_now, top_before = user_top_ids(db, after, envelopes), user_top_ids(db, before, envelopes)
        # Une seule photo (premier récap) ou photo antérieure aux enveloppes : rien à comparer, on ne dit rien du top.
        compared = start is not None and start != latest and top_now is not None and top_before is not None
        if compared:
            entered, left = _names(db, top_now - top_before), _names(db, top_before - top_now)
        else:
            entered, left = [], []
        valued = value_portfolio(db, user.id, today)
        week_change = 0.0
        for v in valued.positions:
            score = db.get(SecurityScore, v.security.id)
            if score is not None and score.perf_1w is not None:
                week_change += v.value * score.perf_1w / (100 + score.perf_1w)  # Ruling 5
        base = valued.total - week_change
        if notify(db, user, "weekly_recap",
                  {"week_end": today, "has_portfolio": bool(valued.positions), "total_value": valued.total,
                   "week_change": round(week_change, 2), "week_change_pct": round(week_change / base * 100, 2) if base else None,
                   "entered": entered, "left": left, "top_compared": compared,
                   "forecasts_checked": len(checked), "forecasts_right": right},
                  dedupe_key=f"weekly_recap:{user.id}:{today:%G-W%V}") is not None:
            sent += 1
    return sent
