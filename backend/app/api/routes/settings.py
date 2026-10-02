from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.current_user import get_current_user
from app.core.db import get_db
from app.models import User, UserSettings
from app.repositories.user_envelopes import user_envelopes
from app.repositories.user_settings import get_user_settings
from app.schemas.settings import EnvelopesIn, EnvelopesOut, SettingsOut, SettingsUpdate
from app.services.envelopes.rules import ENVELOPES

router = APIRouter(tags=["settings"])


def _out(settings: UserSettings) -> SettingsOut:
    return SettingsOut(min_orders_per_year=settings.min_orders_per_year, penalty_fee=settings.penalty_fee, fee_grid=settings.fee_grid)


@router.get("/settings", response_model=SettingsOut)
def read_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SettingsOut:
    return _out(get_user_settings(db, user.id))


@router.put("/settings", response_model=SettingsOut)
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SettingsOut:
    settings = get_user_settings(db, user.id)
    settings.min_orders_per_year = payload.min_orders_per_year
    settings.penalty_fee = payload.penalty_fee
    settings.fee_grid = [t.model_dump() for t in payload.fee_grid]
    db.commit()
    return _out(settings)


@router.get("/settings/envelopes", response_model=EnvelopesOut)
def read_envelopes(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> EnvelopesOut:
    return EnvelopesOut(envelopes=user_envelopes(db, user.id))


@router.put("/settings/envelopes", response_model=EnvelopesOut)
def update_envelopes(payload: EnvelopesIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> EnvelopesOut:
    settings = get_user_settings(db, user.id)
    settings.envelopes = [code for code in ENVELOPES if code in set(payload.envelopes)]
    db.commit()
    return EnvelopesOut(envelopes=user_envelopes(db, user.id))
