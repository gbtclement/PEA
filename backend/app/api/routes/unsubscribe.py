import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.origin import check_origin
from app.api.routes.auth import client_ip, fail
from app.core.config import get_settings
from app.core.current_user import get_now
from app.core.db import get_db
from app.models import User
from app.schemas.auth import NoticeOut
from app.schemas.notifications import UnsubscribeOut
from app.services.notifications.prefs import KINDS, save_prefs
from app.services.notifications.unsubscribe import read_token
from app.services.security_log import log_event

router = APIRouter(tags=["notifications"])

LABELS = {"price_move": "Forte variation de vos titres", "price_alert": "Alertes de prix",
          "daily_recap": "Récap du soir", "weekly_recap": "Récap de la semaine",
          "order_reminder": "Rappel du compteur d'ordres", "score_change": "Changement de score de vos favoris"}


def _target(db: Session, jeton: str, kind: str | None) -> User:
    user_id = read_token(jeton, get_settings().app_secret)
    user = db.get(User, user_id) if user_id else None
    if user is None or (kind is not None and kind not in KINDS):
        raise fail(404, "bad_link", "Ce lien de désinscription n'est pas valable.")
    return user


@router.get("/unsubscribe", response_model=UnsubscribeOut)
def check_unsubscribe_link(jeton: str = Query(max_length=100), kind: str | None = Query(None, alias="type"),
                           db: Session = Depends(get_db)) -> UnsubscribeOut:
    _target(db, jeton, kind)
    return UnsubscribeOut(kind=kind, label=LABELS.get(kind) if kind else None)


@router.post("/unsubscribe", response_model=NoticeOut, dependencies=[Depends(check_origin)])
def unsubscribe(request: Request, jeton: str = Query(max_length=100), kind: str | None = Query(None, alias="type"),
                db: Session = Depends(get_db), now=Depends(get_now)) -> NoticeOut:
    """Lien du mail ou clic unique du service de mail (RFC 8058) : pas de session, le jeton signé suffit."""
    user = _target(db, jeton, kind)
    save_prefs(db, user.id, {kind: False} if kind else {k: False for k in KINDS})
    log_event(db, "unsubscribed", now=now, user_id=user.id, ip=client_ip(request), details={"kind": kind or "all"})
    db.commit()
    return NoticeOut(message=f"Vous ne recevrez plus « {LABELS[kind]} »." if kind
                     else "Vous ne recevrez plus aucune notification. Les mails liés à votre compte restent envoyés.")
