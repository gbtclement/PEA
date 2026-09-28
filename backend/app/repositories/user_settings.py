import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import UserSettings
from app.services.fees import DEFAULT_GRID_JSON, FeeTier, grid_from_json


def get_user_settings(session: Session, user_id: uuid.UUID) -> UserSettings:
    settings = session.get(UserSettings, user_id)
    if settings is None:
        # Deux requêtes simultanées au premier lancement peuvent créer la ligne en même temps.
        session.execute(pg_insert(UserSettings).values(
            user_id=user_id, min_orders_per_year=12, penalty_fee=96.0, fee_grid=list(DEFAULT_GRID_JSON),
        ).on_conflict_do_nothing(index_elements=["user_id"]))
        session.commit()
        settings = session.get(UserSettings, user_id)
    return settings


def user_fee_grid(session: Session, user_id: uuid.UUID) -> tuple[FeeTier, ...]:
    return grid_from_json(get_user_settings(session, user_id).fee_grid)
