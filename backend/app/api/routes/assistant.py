import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.current_user import get_current_user
from app.core.db import get_db
from app.models import User, UserSettings
from app.repositories.assistant import resolve_api_key
from app.repositories.user_settings import get_user_settings
from app.schemas.assistant import AssistantSettingsOut, AssistantSettingsUpdate, ModelOut
from app.services.assistant.catalog import MODELS, get_model
from app.services.secrets import MissingSecretError, encrypt_secret

router = APIRouter(tags=["assistant"])
logger = logging.getLogger(__name__)


def _settings_out(row: UserSettings) -> AssistantSettingsOut:
    _, source = resolve_api_key(row)
    return AssistantSettingsOut(configured=source is not None, source=source, model=get_model(row.ai_model).id,
                                models=[ModelOut(id=m.id, label=m.label) for m in MODELS])


@router.get("/assistant/settings", response_model=AssistantSettingsOut)
def read_assistant_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> AssistantSettingsOut:
    return _settings_out(get_user_settings(db, user.id))


@router.put("/assistant/settings", response_model=AssistantSettingsOut)
def update_assistant_settings(
    payload: AssistantSettingsUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> AssistantSettingsOut:
    row = get_user_settings(db, user.id)
    row.ai_model = payload.model
    if payload.remove_key:
        row.anthropic_key_enc = None
    elif payload.api_key:
        try:
            row.anthropic_key_enc = encrypt_secret(payload.api_key, get_settings().app_secret)
        except MissingSecretError:
            db.rollback()
            raise HTTPException(status_code=503, detail="Ajoutez APP_SECRET dans le fichier .env pour enregistrer une clé.")
    db.commit()
    return _settings_out(row)
