import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_google_client
from app.api.routes.auth import fail
from app.core.config import get_settings
from app.core.current_user import get_now, require_admin
from app.core.db import get_db
from app.models import User
from app.repositories.app_settings import get_app_settings
from app.schemas.admin import (
    AdminSettingsIn, AdminSettingsOut, AdminUserListOut, AdminUserOut, AdminUserUpdate, ConfigStatusOut, DeleteUserIn,
    ModelChoice, SortKey,
)
from app.schemas.auth import NoticeOut
from app.services.admin.users import PAGE_SIZE, AdminError, delete_user, list_users, update_user
from app.services.assistant.catalog import MODELS
from app.services.auth.google import GoogleClient
from app.services.mail.outbox import enqueue
from app.services.security_log import log_event

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

_USER_FIELDS = ("id", "email", "first_name", "last_name", "role", "is_premium", "has_password", "has_google",
                "created_at", "last_login_at")


def _out(user: User) -> AdminUserOut:
    return AdminUserOut(**{k: getattr(user, k) for k in _USER_FIELDS}, verified=user.email_verified_at is not None)


def _target(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise fail(404, "not_found", "Compte introuvable.")
    return user


@router.get("/users", response_model=AdminUserListOut)
def admin_list_users(q: str = Query("", max_length=100), sort: SortKey = "created_at",
                     order: str = Query("desc", pattern="^(asc|desc)$"), page: int = Query(1, ge=1),
                     db: Session = Depends(get_db)) -> AdminUserListOut:
    result = list_users(db, q=q, sort=sort, order=order, page=page)
    return AdminUserListOut(items=[_out(u) for u in result.items], total=result.total, page=page, page_size=PAGE_SIZE)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def admin_update_user(user_id: uuid.UUID, payload: AdminUserUpdate, db: Session = Depends(get_db),
                      actor: User = Depends(require_admin), now: datetime = Depends(get_now)) -> AdminUserOut:
    target = _target(db, user_id)
    try:
        update_user(db, actor=actor, target=target, changes=payload.model_dump(exclude_none=True), now=now)
        db.commit()
    except AdminError as error:  # levée avant toute écriture : rien à annuler
        raise fail(error.status, error.code, error.message)
    except IntegrityError:  # adresse prise entre la vérification et l'écriture
        db.rollback()
        raise fail(409, "email_taken", "Cette adresse vient d'être prise par un autre compte.")
    return _out(target)


@router.delete("/users/{user_id}", status_code=204)
def admin_delete_user(user_id: uuid.UUID, payload: DeleteUserIn, db: Session = Depends(get_db),
                      actor: User = Depends(require_admin), now: datetime = Depends(get_now)) -> Response:
    target = _target(db, user_id)
    try:
        delete_user(db, actor=actor, target=target, confirm_email=payload.confirm_email, now=now)
    except AdminError as error:  # levée avant toute écriture : rien à annuler
        raise fail(error.status, error.code, error.message)
    db.commit()
    return Response(status_code=204)


def _settings_out(db: Session) -> AdminSettingsOut:
    row = get_app_settings(db)
    return AdminSettingsOut(ai_model=row.ai_model, ai_monthly_cost_limit_usd=row.ai_monthly_cost_limit_usd,
                            models=[ModelChoice(id=m.id, label=m.label) for m in MODELS])


@router.get("/settings", response_model=AdminSettingsOut)
def admin_read_settings(db: Session = Depends(get_db)) -> AdminSettingsOut:
    return _settings_out(db)


@router.put("/settings", response_model=AdminSettingsOut)
def admin_update_settings(payload: AdminSettingsIn, db: Session = Depends(get_db),
                          actor: User = Depends(require_admin), now: datetime = Depends(get_now)) -> AdminSettingsOut:
    row = get_app_settings(db)
    row.ai_model, row.ai_monthly_cost_limit_usd = payload.ai_model, payload.ai_monthly_cost_limit_usd
    log_event(db, "admin_settings_updated", now=now, actor_id=actor.id, details=payload.model_dump())
    db.commit()
    return _settings_out(db)


@router.get("/config-status", response_model=ConfigStatusOut)
def admin_config_status(google: GoogleClient | None = Depends(get_google_client)) -> ConfigStatusOut:
    """Ce qui est renseigné dans .env : oui ou non, jamais la valeur."""
    s = get_settings()
    return ConfigStatusOut(claude=bool(s.anthropic_api_key), smtp=bool(s.smtp_host), google=google is not None,
                           turnstile=bool(s.turnstile_secret_key and s.turnstile_site_key),
                           app_secret=bool(s.app_secret) and s.app_secret != "change-me",
                           admin_email=bool(s.admin_email))


@router.post("/test-email", response_model=NoticeOut, status_code=202)
def admin_test_email(db: Session = Depends(get_db), actor: User = Depends(require_admin)) -> NoticeOut:
    enqueue(db, "test", to=actor.email, user_id=actor.id, context={"first_name": actor.first_name})
    db.commit()
    return NoticeOut(message=f"Mail de test mis en file d'attente pour {actor.email}.")
