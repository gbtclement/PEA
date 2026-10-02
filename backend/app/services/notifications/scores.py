"""Photo des scores chaque soir, et N6 : changement de score d'un favori. Pas de commit ici."""
from collections.abc import Sequence
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import Favorite, ScoreSnapshot, Security, SecurityScore
from app.repositories.envelopes import envelope_clause
from app.repositories.scores import top_security_ids
from app.repositories.user_envelopes import user_envelopes
from app.services.notifications.prefs import recipients
from app.services.notifications.send import notify

TOP_SIZE = 10
BIG_MOVE = 10.0  # points de score


def take_score_snapshot(db: Session, day: date) -> None:
    db.execute(delete(ScoreSnapshot).where(ScoreSnapshot.day == day))
    ranks = {sid: rank for rank, sid in enumerate(top_security_ids(db, TOP_SIZE), start=1)}
    for sid, total, pool in db.execute(select(SecurityScore.security_id, SecurityScore.total, SecurityScore.eligible_for_top)
                                       .where(SecurityScore.total.is_not(None))):
        db.add(ScoreSnapshot(day=day, security_id=sid, total=total, top_rank=ranks.get(sid), top_pool=pool))
    db.flush()


def user_top_ids(db: Session, rows: dict[int, ScoreSnapshot], envelopes: Sequence[str], size: int = TOP_SIZE) -> set[int]:
    """Top 10 d'un membre ce jour-là : candidats du soir, filtrés par ses enveloppes (statut actuel), meilleurs scores."""
    candidates = [row for row in rows.values() if row.top_pool]
    clause = envelope_clause(envelopes)
    if clause is not None:
        allowed = set(db.scalars(select(Security.id).where(Security.id.in_([r.security_id for r in candidates]), clause)))
        candidates = [row for row in candidates if row.security_id in allowed]
    return {row.security_id for row in sorted(candidates, key=lambda r: -r.total)[:size]}


def snapshot(db: Session, day: date) -> dict[int, ScoreSnapshot]:
    return {row.security_id: row for row in db.scalars(select(ScoreSnapshot).where(ScoreSnapshot.day == day))}


def previous_day(db: Session, before: date) -> date | None:
    return db.scalar(select(func.max(ScoreSnapshot.day)).where(ScoreSnapshot.day < before))


def score_changes(before: dict[int, ScoreSnapshot], after: dict[int, ScoreSnapshot], ids: set[int],
                  top_before: set[int], top_after: set[int]) -> list[dict]:
    items = []
    for sid in sorted(ids):
        old, new = before.get(sid), after.get(sid)
        if old is None or new is None:
            continue
        if sid in top_after and sid not in top_before:
            change = "entered"
        elif sid in top_before and sid not in top_after:
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
        envelopes = user_envelopes(db, user.id)
        items = score_changes(before, after, favorites, user_top_ids(db, before, envelopes), user_top_ids(db, after, envelopes))
        if not items:
            continue
        names = dict(db.execute(select(Security.id, Security.name).where(Security.id.in_([i["security_id"] for i in items]))).all())
        for item in items:
            item["name"] = names[item["security_id"]]
        if notify(db, user, "score_change", {"items": items}, dedupe_key=f"score_change:{user.id}:{day}") is not None:
            sent += 1
    return sent
