from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.cookies import set_auth_cookies, set_device_cookie
from app.core.config import get_settings
from app.core.current_user import get_now
from app.core.db import get_db
from app.core.security import password_problem
from app.models import User
from app.schemas.auth import EmailIn, MeOut, MessageOut, RegisterIn, VerifyEmailIn
from app.services.auth import accounts
from app.services.auth.codes import CodeCheck
from app.services.auth.devices import remember_device
from app.services.auth.sessions import DEVICE_COOKIE, open_session

router = APIRouter(prefix="/auth", tags=["auth"])

CODE_SENT = MessageOut(message="Si cette adresse peut recevoir un code, il vient d'y être envoyé.")
CODE_ERRORS = {
    CodeCheck.INVALID: ("invalid_code", "Code incorrect."),
    CodeCheck.EXPIRED: ("code_expired", "Ce code a expiré : demandez-en un nouveau."),
    CodeCheck.TOO_MANY: ("too_many_attempts", "Trop d'essais : demandez un nouveau code."),
}


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


@router.post("/register", response_model=MessageOut, status_code=202)
def register(payload: RegisterIn, db: Session = Depends(get_db), now: datetime = Depends(get_now)) -> MessageOut:
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


@router.post("/resend-code", response_model=MessageOut, status_code=202)
def resend_code(payload: EmailIn, db: Session = Depends(get_db), now: datetime = Depends(get_now)) -> MessageOut:
    accounts.resend_code(db, payload.email, now)
    db.commit()
    return CODE_SENT
