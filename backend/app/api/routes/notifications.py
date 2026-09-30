import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.auth import fail
from app.core.current_user import get_account_user, get_current_user
from app.core.db import get_db
from app.models import PriceAlert, Security, User
from app.schemas.notifications import NotificationPrefsIn, NotificationPrefsOut, PriceAlertIn, PriceAlertOut, PriceAlertUpdate
from app.services.fx import currency_for_market
from app.services.notifications.prefs import get_prefs, save_prefs
from app.services.notifications.price_alerts import AlertRefused, check_new_threshold, current_price

router = APIRouter(tags=["notifications"])


@router.get("/me/notifications", response_model=NotificationPrefsOut)
def read_notification_prefs(db: Session = Depends(get_db), user: User = Depends(get_account_user)) -> NotificationPrefsOut:
    return NotificationPrefsOut.model_validate(get_prefs(db, user.id))


@router.put("/me/notifications", response_model=NotificationPrefsOut)
def write_notification_prefs(payload: NotificationPrefsIn, db: Session = Depends(get_db),
                             user: User = Depends(get_account_user)) -> NotificationPrefsOut:
    """Ouverte même avec des CGU périmées : se retirer des mails reste toujours possible (spec 6.4)."""
    row = save_prefs(db, user.id, payload.model_dump())
    db.commit()
    return NotificationPrefsOut.model_validate(row)


def _out(db: Session, alert: PriceAlert) -> PriceAlertOut:
    security = db.get(Security, alert.security_id)
    return PriceAlertOut(id=alert.id, security_id=security.id, symbol=security.symbol, name=security.name,
                         currency=currency_for_market(security.market), direction=alert.direction, price=alert.price,
                         current_price=current_price(db, security.id), active=alert.active,
                         triggered_at=alert.triggered_at, created_at=alert.created_at)


def _own(db: Session, user: User, alert_id: uuid.UUID) -> PriceAlert:
    alert = db.get(PriceAlert, alert_id)
    if alert is None or alert.user_id != user.id:
        raise fail(404, "not_found", "Alerte introuvable.")
    return alert


@router.get("/me/price-alerts", response_model=list[PriceAlertOut])
def list_price_alerts(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[PriceAlertOut]:
    rows = db.scalars(select(PriceAlert).where(PriceAlert.user_id == user.id)
                      .order_by(PriceAlert.active.desc(), PriceAlert.created_at.desc()))
    return [_out(db, alert) for alert in rows]


@router.post("/me/price-alerts", response_model=PriceAlertOut, status_code=201)
def create_price_alert(payload: PriceAlertIn, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)) -> PriceAlertOut:
    if db.get(Security, payload.security_id) is None:
        raise fail(404, "not_found", "Titre introuvable.")
    try:
        check_new_threshold(db, user.id, payload.security_id, payload.direction, payload.price)
    except AlertRefused as refused:
        raise fail(refused.status, refused.code, refused.message)
    alert = PriceAlert(user_id=user.id, **payload.model_dump())
    db.add(alert)
    db.commit()
    return _out(db, alert)


@router.patch("/me/price-alerts/{alert_id}", response_model=PriceAlertOut)
def update_price_alert(alert_id: uuid.UUID, payload: PriceAlertUpdate, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)) -> PriceAlertOut:
    alert = _own(db, user, alert_id)
    changes = payload.model_dump(exclude_none=True)
    direction, price = changes.get("direction", alert.direction), changes.get("price", alert.price)
    if changes.get("active", alert.active):  # réarmer ou modifier une alerte active : mêmes règles qu'à la création
        try:
            check_new_threshold(db, user.id, alert.security_id, direction, price, ignore=alert.id)
        except AlertRefused as refused:
            raise fail(refused.status, refused.code, refused.message)
    if changes.get("active") and not alert.active:
        alert.triggered_at = None
    alert.direction, alert.price, alert.active = direction, price, changes.get("active", alert.active)
    db.commit()
    return _out(db, alert)


@router.delete("/me/price-alerts/{alert_id}", status_code=204)
def delete_price_alert(alert_id: uuid.UUID, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)) -> Response:
    db.delete(_own(db, user, alert_id))
    db.commit()
    return Response(status_code=204)
