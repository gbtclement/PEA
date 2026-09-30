import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.cookies import clear_auth_cookies
from app.api.deps import get_breach_checker
from app.api.routes.auth import CODE_ERRORS, check_password_rules, client_ip, fail, mail_allowed
from app.core.config import get_settings
from app.core.current_user import get_auth_session, get_account_user, get_now
from app.core.db import get_db
from app.core.security import normalize_email
from app.models import AuthSession, DataExport, User
from app.schemas.auth import MeOut, NoticeOut
from app.schemas.me import AcceptTermsIn, CodeIn, DeleteAccountIn, ExportOut, EmailChangeIn, PasswordChangeIn, ProfileIn, SessionOut
from app.services.auth import accounts, profile
from app.services.auth.breach import BreachChecker
from app.services.auth.codes import CodeCheck
from app.services.auth.sessions import revoke_session
from app.services.privacy import export
from app.services.privacy.erasure import erase_account
from app.services.security_log import log_event

router = APIRouter(tags=["account"])

WRONG_PASSWORD = ("wrong_password", "Mot de passe actuel incorrect.")


@router.get("/me", response_model=MeOut)
def read_me(user: User = Depends(get_account_user)) -> MeOut:
    return MeOut.model_validate(user)


@router.patch("/me", response_model=MeOut)
def update_me(payload: ProfileIn, db: Session = Depends(get_db), user: User = Depends(get_account_user)) -> MeOut:
    user.first_name, user.last_name = payload.first_name, payload.last_name
    db.commit()
    return MeOut.model_validate(user)


@router.post("/me/password", response_model=NoticeOut)
def change_password(payload: PasswordChangeIn, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(get_account_user), auth: AuthSession = Depends(get_auth_session),
                    now: datetime = Depends(get_now), breach: BreachChecker = Depends(get_breach_checker)) -> NoticeOut:
    if not profile.password_ok(user, payload.current_password):
        raise fail(400, *WRONG_PASSWORD)  # avant Have I Been Pwned : pas de relais gratuit
    check_password_rules(payload.new_password, breach)
    profile.change_password(db, user, payload.new_password, keep_session=auth, now=now, ip=client_ip(request))
    db.commit()
    return NoticeOut(message="Mot de passe enregistré. Vos autres appareils ont été déconnectés.")


@router.post("/me/email", response_model=NoticeOut, status_code=202)
def request_email_change(payload: EmailChangeIn, request: Request, db: Session = Depends(get_db),
                         user: User = Depends(get_account_user), now: datetime = Depends(get_now)) -> NoticeOut:
    if not profile.password_ok(user, payload.password):
        raise fail(400, *WRONG_PASSWORD)
    new_email = normalize_email(payload.new_email)
    if mail_allowed(db, new_email, client_ip(request) or "inconnue", now):
        profile.request_email_change(db, user, new_email, now)
    db.commit()
    return NoticeOut(message="Si cette adresse peut être utilisée, un code vient d'y être envoyé.")


@router.post("/me/email/verify", response_model=MeOut)
def confirm_email_change(payload: CodeIn, request: Request, db: Session = Depends(get_db),
                         user: User = Depends(get_account_user), auth: AuthSession = Depends(get_auth_session),
                         now: datetime = Depends(get_now)) -> MeOut:
    try:
        result = profile.confirm_email_change(db, user, payload.code, now, client_ip(request), keep_session=auth)
    except profile.EmailTaken:
        db.commit()  # le code est consommé : il faudra en redemander un
        raise fail(409, "email_taken", "Cette adresse vient d'être prise par un autre compte.")
    if result != CodeCheck.OK:
        db.commit()  # enregistre l'essai raté
        raise fail(400, *CODE_ERRORS[result])
    db.commit()
    return MeOut.model_validate(user)


@router.get("/me/sessions", response_model=list[SessionOut])
def list_sessions(db: Session = Depends(get_db), auth: AuthSession = Depends(get_auth_session),
                  user: User = Depends(get_account_user), now: datetime = Depends(get_now)) -> list[SessionOut]:
    rows = db.scalars(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.expires_at > now)
                      .order_by(AuthSession.last_seen_at.desc()))
    return [SessionOut(id=r.id, device=r.device, ip=r.ip, created_at=r.created_at, last_seen_at=r.last_seen_at,
                       current=r.id == auth.id) for r in rows]


@router.delete("/me/sessions/{session_id}", status_code=204)
def revoke_one_session(session_id: uuid.UUID, request: Request, response: Response, db: Session = Depends(get_db),
                       auth: AuthSession = Depends(get_auth_session), user: User = Depends(get_account_user),
                       now: datetime = Depends(get_now)) -> Response:
    row = db.get(AuthSession, session_id)
    if row is None or row.user_id != user.id:
        raise fail(404, "not_found", "Appareil introuvable.")
    revoke_session(db, row.id)
    log_event(db, "session_revoked", now=now, user_id=user.id, ip=client_ip(request))
    db.commit()
    if row.id == auth.id:
        clear_auth_cookies(response, get_settings())
    response.status_code = 204
    return response


@router.delete("/me/sessions", status_code=204)
def revoke_other_sessions(request: Request, db: Session = Depends(get_db), auth: AuthSession = Depends(get_auth_session),
                          user: User = Depends(get_account_user), now: datetime = Depends(get_now)) -> Response:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.id != auth.id))
    log_event(db, "session_revoked", now=now, user_id=user.id, ip=client_ip(request), details={"all_others": True})
    db.commit()
    return Response(status_code=204)


@router.post("/me/accept-terms", response_model=MeOut)
def accept_terms(payload: AcceptTermsIn, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(get_account_user), now: datetime = Depends(get_now)) -> MeOut:
    accounts.accept_terms(user, now)
    log_event(db, "terms_accepted", now=now, user_id=user.id, ip=client_ip(request), details={"version": user.terms_version})
    db.commit()
    return MeOut.model_validate(user)


REAUTH_WINDOW = timedelta(minutes=5)  # compte sans mot de passe : reconnexion Google récente exigée (spec 4.1)


@router.delete("/me", status_code=204)
def delete_account(payload: DeleteAccountIn, response: Response, db: Session = Depends(get_db),
                   user: User = Depends(get_account_user), auth: AuthSession = Depends(get_auth_session),
                   now: datetime = Depends(get_now)) -> Response:
    if normalize_email(payload.confirm_email) != user.email:
        raise fail(400, "confirm_mismatch", "L'adresse retapée ne correspond pas à votre compte.")
    if user.has_password:
        if not profile.password_ok(user, payload.password):
            raise fail(400, *WRONG_PASSWORD)
    elif now - auth.created_at > REAUTH_WINDOW:
        raise fail(403, "reauth_required", "Reconnectez-vous avec Google, puis confirmez dans les 5 minutes.")
    if user.role == "admin" and db.scalar(select(func.count()).select_from(User).where(User.role == "admin")) <= 1:
        raise fail(400, "last_admin", "Vous êtes le seul administrateur : nommez-en un autre avant de supprimer votre compte.")
    erase_account(db, user, now=now)
    db.commit()
    clear_auth_cookies(response, get_settings())
    response.status_code = 204
    return response


@router.post("/me/export", response_model=ExportOut, status_code=202)
def request_data_export(request: Request, db: Session = Depends(get_db), user: User = Depends(get_account_user),
                        now: datetime = Depends(get_now)) -> ExportOut:
    try:
        row = export.request_export(db, user, now)
    except export.ExportRefused as refused:
        raise fail(refused.status, refused.code, refused.message)
    log_event(db, "data_export", now=now, user_id=user.id, ip=client_ip(request))
    db.commit()
    return ExportOut.model_validate(row)


@router.get("/me/export", response_model=ExportOut | None)
def latest_data_export(db: Session = Depends(get_db), user: User = Depends(get_account_user)) -> ExportOut | None:
    row = export.latest_export(db, user)
    return ExportOut.model_validate(row) if row else None


@router.get("/me/export/{export_id}")
def download_data_export(export_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_account_user),
                         now: datetime = Depends(get_now)) -> Response:
    row = db.get(DataExport, export_id)
    if row is None or row.user_id != user.id or row.status != "ready" or row.expires_at <= now:
        raise fail(404, "not_found", "Export introuvable ou expiré : demandez-en un nouveau.")
    name = f"pea-radar-mes-donnees-{row.ready_at:%Y-%m-%d}.json"
    return Response(row.content, media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})
