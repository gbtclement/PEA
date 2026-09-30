from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AppSettings


def get_app_settings(db: Session) -> AppSettings:
    """La ligne unique des réglages communs ; créée avec les valeurs par défaut si elle manque."""
    row = db.get(AppSettings, 1)
    if row is None:
        db.execute(pg_insert(AppSettings).values(id=1, ai_model=get_settings().assistant_model,
                                                 ai_monthly_cost_limit_usd=5.0)
                   .on_conflict_do_nothing(index_elements=["id"]))
        db.flush()
        row = db.get(AppSettings, 1)
    return row
