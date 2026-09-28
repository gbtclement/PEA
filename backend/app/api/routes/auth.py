from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.cookies import clear_auth_cookies, set_auth_cookies, set_device_cookie
from app.api.deps import get_captcha
from app.core.config import get_settings
from app.core.current_user import get_auth_session, get_now
from app.core.db import get_db
from app.core.security import normalize_email, password_problem
from app.models import AuthSession, User
from app.schemas.auth import (
    EmailIn, LoginIn, MeOut, NoticeOut, RegisterIn, ResetPasswordIn, TokenIn, VerifyEmailIn,
)
from app.services import ratelimit
from app.services.auth import accounts
from app.services.auth.captcha import CaptchaVerifier
from app.services.auth.codes import CodeCheck
from app.services.auth.devices import remember_device
from app.services.auth.sessions import DEVICE_COOKIE, SESSION_COOKIE, open_session, resolve_session, revoke_session
from app.services.security_log import log_event

router = APIRouter(prefix="/auth", tags=["auth"])

CODE_SENT = NoticeOut(message="Si cette adresse peut recevoir un code, il vient d'y être envoyé.")
CODE_ERRORS = {
    CodeCheck.INVALID: ("invalid_code", "Code incorrect."),
    CodeCheck.EXPIRED: ("code_expired", "Ce code a expiré : demandez-en un nouveau."),
    CodeCheck.TOO_MANY: ("too_many_attempts", "Trop d'essais : demandez un nouveau code."),
}
INVALID_TOKEN = ("invalid_token", "Ce lien n'est plus valable : refaites une demande.")
LOCKED = ("account_locked", "Trop d'essais pour ce compte : réessayez dans 15 minutes.")
TOO_MANY = ("too_many_requests", "Trop de tentatives depuis votre connexion : réessayez plus tard.")
CAPTCHA = ("captcha_required", "Confirmez que vous n'êtes pas un robot, puis réessayez.")
RESET_SENT = NoticeOut(message="Si un compte utilise cette adresse, un lien vient d'y être envoyé.")


def fail(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status, detail={"code": code, "message": message})


def check_password_rules(password: str) -> None:
    problem = password_problem(password)
    if problem:
        raise fail(400, "weak_password", problem)


def client_ip(request: Request) -> str | None:
    # nginx ajoute l'IP du visiteur en dernier dans X-Forwarded-For ; c'est le seul proxy de confiance.
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else None


def start_session(db: Session, user: User, request: Request, response: Response, *, persistent: bool,
                  now: datetime, alert_new_device: bool) -> None:
    """Ouvre la session, reconnaît l'appareil et pose les cookies. Le commit est fait ici."""
    settings = get_settings()
    new = open_session(db, user, persistent=persistent, ip=client_ip(request),
                       user_agent=request.headers.get("User-Agent"), now=now, settings=settings)
    device_token, is_new_device = remember_device(db, user, request.cookies.get(DEVICE_COOKIE), now)
    if alert_new_device and is_new_device:
        accounts.alert_new_device(db, user, new.session.device, now)
    db.commit()
    set_auth_cookies(response, new, settings)
    set_device_cookie(response, device_token, settings)


@router.post("/register", response_model=NoticeOut, status_code=202)
def register(payload: RegisterIn, db: Session = Depends(get_db), now: datetime = Depends(get_now)) -> NoticeOut:
    check_password_rules(payload.password)
    accounts.register(db, first_name=payload.first_name, last_name=payload.last_name, email=payload.email,
                      password=payload.password, now=now)
    db.commit()
    return CODE_SENT


@router.post("/verify-email", response_model=MeOut)
def verify_email(payload: VerifyEmailIn, request: Request, response: Response, db: Session = Depends(get_db),
                 now: datetime = Depends(get_now)) -> MeOut:
    user, result = accounts.verify_email(db, payload.email, payload.code, now)
    if user is None:
        db.commit()  # enregistre l'essai raté
        raise fail(400, *CODE_ERRORS[result])
    start_session(db, user, request, response, persistent=True, now=now, alert_new_device=False)
    return MeOut.model_validate(user)


@router.post("/resend-code", response_model=NoticeOut, status_code=202)
def resend_code(payload: EmailIn, db: Session = Depends(get_db), now: datetime = Depends(get_now)) -> NoticeOut:
    accounts.resend_code(db, payload.email, now)
    db.commit()
    return CODE_SENT


@router.post("/login", response_model=MeOut)
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db),
          now: datetime = Depends(get_now), captcha: CaptchaVerifier = Depends(get_captcha)) -> MeOut:
    ip, email = client_ip(request) or "inconnue", normalize_email(payload.email)
    if ratelimit.over(db, "login_ip", ip, now):
        raise fail(429, *TOO_MANY)
    if ratelimit.over(db, "login_account", email, now):  # même réponse que le compte existe ou non
        raise fail(429, *LOCKED)
    failures = max(ratelimit.count(db, "login_account", email, now), ratelimit.count(db, "login_ip", ip, now))
    if failures >= ratelimit.CAPTCHA_AFTER and not captcha.verify(payload.captcha, ip):
        raise fail(400, *CAPTCHA)
    user = accounts.authenticate(db, email, payload.password)
    if user is None:
        known = accounts.find_user(db, email)
        ratelimit.record(db, "login_account", email, now)
        ratelimit.record(db, "login_ip", ip, now)
        log_event(db, "login_failed", now=now, user_id=known.id if known else None, ip=ip)
        if ratelimit.over(db, "login_account", email, now):
            log_event(db, "locked", now=now, user_id=known.id if known else None, ip=ip)
            if known is not None:
                known.locked_until = now + ratelimit.FIFTEEN_MINUTES
        db.commit()
        raise fail(401, "invalid_credentials", "Adresse mail ou mot de passe incorrect.")
    if user.email_verified_at is None:
        accounts.resend_code(db, user.email, now)
        db.commit()
        raise fail(403, "email_not_verified", "Validez d'abord votre adresse : un code vient de vous être envoyé.")
    ratelimit.clear(db, "login_account", email)
    user.failed_logins, user.locked_until = 0, None
    log_event(db, "login_ok", now=now, user_id=user.id, ip=ip, details={"method": "password"})
    previous = resolve_session(db, request.cookies.get(SESSION_COOKIE), now=now, settings=get_settings())
    if previous is not None:
        revoke_session(db, previous.id)  # jamais deux sessions pour le même cookie
    start_session(db, user, request, response, persistent=payload.remember, now=now, alert_new_device=True)
    return MeOut.model_validate(user)


@router.post("/logout", status_code=204)
def logout(response: Response, auth: AuthSession | None = Depends(get_auth_session), db: Session = Depends(get_db)) -> Response:
    if auth is not None:
        revoke_session(db, auth.id)
        db.commit()
    clear_auth_cookies(response, get_settings())
    response.status_code = 204
    return response


@router.post("/forgot-password", response_model=NoticeOut, status_code=202)
def forgot_password(payload: EmailIn, db: Session = Depends(get_db), now: datetime = Depends(get_now)) -> NoticeOut:
    accounts.request_password_reset(db, payload.email, now)
    db.commit()
    return RESET_SENT


@router.post("/reset-password", response_model=NoticeOut)
def reset_password(payload: ResetPasswordIn, db: Session = Depends(get_db), now: datetime = Depends(get_now)) -> NoticeOut:
    check_password_rules(payload.password)
    if accounts.reset_password(db, payload.token, payload.password, now) is None:
        raise fail(400, *INVALID_TOKEN)
    db.commit()
    return NoticeOut(message="Mot de passe modifié : vous pouvez vous connecter.")


@router.post("/not-me", response_model=NoticeOut)
def not_me(payload: TokenIn, db: Session = Depends(get_db), now: datetime = Depends(get_now)) -> NoticeOut:
    if accounts.not_me(db, payload.token, now) is None:
        raise fail(400, *INVALID_TOKEN)
    db.commit()
    return NoticeOut(message="Tous vos appareils ont été déconnectés. Un lien pour choisir un nouveau mot de passe "
                              "vient de vous être envoyé.")
