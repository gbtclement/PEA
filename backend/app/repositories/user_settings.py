from sqlalchemy.orm import Session

from app.models import UserSettings
from app.services.fees import DEFAULT_GRID_JSON, FeeTier, grid_from_json


def get_user_settings(session: Session, user_id: int) -> UserSettings:
    settings = session.get(UserSettings, user_id)
    if settings is None:
        settings = UserSettings(user_id=user_id, min_orders_per_year=12, penalty_fee=96.0, fee_grid=list(DEFAULT_GRID_JSON))
        session.add(settings)
        session.commit()
    return settings


def user_fee_grid(session: Session, user_id: int) -> tuple[FeeTier, ...]:
    return grid_from_json(get_user_settings(session, user_id).fee_grid)
