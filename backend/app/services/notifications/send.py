"""Envoi d'une notification N1 à N6 : lien de désinscription, en-têtes « un clic », file d'envoi."""
import logging
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import User
from app.services.mail.outbox import enqueue
from app.services.notifications.unsubscribe import make_token

logger = logging.getLogger(__name__)


def notifications_ready() -> bool:
    """Sans APP_SECRET, pas de lien de désinscription possible : aucune notification ne part."""
    if get_settings().app_secret:
        return True
    logger.warning("APP_SECRET vide : les notifications ne sont pas envoyées.")
    return False


def notify(db: Session, user: User, kind: str, context: dict, *, dedupe_key: str) -> int | None:
    """Met la notification en file (pas de commit). None si `dedupe_key` a déjà servi."""
    settings = get_settings()
    base = settings.public_base_url.rstrip("/")
    query = urlencode({"jeton": make_token(user.id, settings.app_secret), "type": kind})
    headers = {"List-Unsubscribe": f"<{base}/api/unsubscribe?{query}>",
               "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}
    context = {**context, "first_name": user.first_name, "manage_url": f"{base}/reglages#notifications",
               "unsubscribe_url": f"{base}/desinscription?{query}"}
    return enqueue(db, kind, to=user.email, user_id=user.id, context=context, dedupe_key=dedupe_key, headers=headers)
