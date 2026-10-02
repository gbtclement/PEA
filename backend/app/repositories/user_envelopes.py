import uuid

from sqlalchemy.orm import Session

from app.models import UserSettings
from app.services.envelopes.rules import ENVELOPES


def user_envelopes(session: Session, user_id: uuid.UUID | None) -> list[str]:
    """Enveloppes choisies (ordre du registre) ; [] pour un visiteur ou un compte sans réglages. Ne crée aucune ligne."""
    if user_id is None:
        return []
    settings = session.get(UserSettings, user_id)
    chosen = set(settings.envelopes or []) if settings else set()
    return [code for code in ENVELOPES if code in chosen]
