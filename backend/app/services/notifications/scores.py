"""Photo des scores chaque soir, et N6 : changement de score d'un favori. Pas de commit ici."""
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import Favorite, ScoreSnapshot, Security, SecurityScore
from app.repositories.scores import top_security_ids
from app.services.notifications.prefs import recipients
from app.services.notifications.send import notify

TOP_SIZE = 10
BIG_MOVE = 10.0  # points de score


def take_score_snapshot(db: Session, day: date) -> None:
    db.execute(delete(ScoreSnapshot).where(ScoreSnapshot.day == day))
    ranks = {sid: rank for rank, sid in enumerate(top_security_ids(db, TOP_SIZE), start=1)}
    for sid, total in db.execute(select(SecurityScore.security_id, SecurityScore.total)
                                 .where(SecurityScore.total.is_not(None))):
        db.add(ScoreSnapshot(day=day, security_id=sid, total=total, top_rank=ranks.get(sid)))
    db.flush()


def snapshot(db: Session, day: date) -> dict[int, ScoreSnapshot]:
    return {row.security_id: row for row in db.scalars(select(ScoreSnapshot).where(ScoreSnapshot.day == day))}


def previous_day(db: Session, before: date) -> date | None:
    return db.scalar(select(func.max(ScoreSnapshot.day)).where(ScoreSnapshot.day < before))


def score_changes(before: dict[int, ScoreSnapshot], after: dict[int, ScoreSnapshot], ids: set[int]) -> list[dict]:
    items = []
    for sid in sorted(ids):
        old, new = before.get(sid), after.get(sid)
        if old is None or new is None:
            continue
        if new.top_rank and not old.top_rank:
            change = "entered"
        elif old.top_rank and not new.top_rank:
            change = "left"
        elif abs(new.total - old.total) >= BIG_MOVE:
            change = "up" if new.total > old.total else "down"
        else:
            continue
        items.append({"security_id": sid, "before": round(old.total), "after": round(new.total), "change": change})
    return items


def notify_score_changes(db: Session, day: date) -> int:
    prev = previous_day(db, day)
    if prev is None:
        return 0
    before, after = snapshot(db, prev), snapshot(db, day)
    sent = 0
    for user, _ in recipients(db, "score_change"):
        favorites = set(db.scalars(select(Favorite.security_id).where(Favorite.user_id == user.id)))
        items = score_changes(before, after, favorites)
        if not items:
            continue
        names = dict(db.execute(select(Security.id, Security.name).where(Security.id.in_([i["security_id"] for i in items]))).all())
        for item in items:
            item["name"] = names[item["security_id"]]
        if notify(db, user, "score_change", {"items": items}, dedupe_key=f"score_change:{user.id}:{day}") is not None:
            sent += 1
    return sent
