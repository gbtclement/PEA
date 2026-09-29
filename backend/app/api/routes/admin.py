import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.routes.auth import fail
from app.core.current_user import get_now, require_admin
from app.core.db import get_db
from app.models import User
from app.schemas.admin import AdminUserListOut, AdminUserOut, AdminUserUpdate, DeleteUserIn, SortKey
from app.services.admin.users import PAGE_SIZE, AdminError, delete_user, list_users, update_user

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
    except AdminError as error:  # levée avant toute écriture : rien à annuler
        raise fail(error.status, error.code, error.message)
    db.commit()
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
