import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import AiUsage

PARIS = ZoneInfo("Europe/Paris")


def month_key(now: datetime) -> str:
    """Mois civil à l'heure de Paris, « AAAA-MM » : la limite repart le 1er à minuit."""
    return now.astimezone(PARIS).strftime("%Y-%m")


def month_spent(db: Session, user_id: uuid.UUID, now: datetime) -> float:
    row = db.get(AiUsage, (user_id, month_key(now)))
    return row.cost_usd if row else 0.0


def add_cost(db: Session, user_id: uuid.UUID, cost: float, now: datetime) -> None:
    """Ajoute le coût d'une réponse au mois en cours (dans la transaction de l'appelant)."""
    stmt = pg_insert(AiUsage).values(user_id=user_id, month=month_key(now), cost_usd=cost)
    db.execute(stmt.on_conflict_do_update(index_elements=["user_id", "month"],
                                          set_={"cost_usd": AiUsage.cost_usd + stmt.excluded.cost_usd}))
