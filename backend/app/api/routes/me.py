from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_breach_checker
from app.api.routes.auth import CODE_ERRORS, check_password_rules, client_ip, fail, mail_allowed
from app.core.current_user import get_auth_session, get_current_user, get_now
from app.core.db import get_db
from app.core.security import normalize_email
from app.models import AuthSession, User
from app.schemas.auth import MeOut, NoticeOut
from app.schemas.me import CodeIn, EmailChangeIn, PasswordChangeIn, ProfileIn
from app.services.auth import profile
from app.services.auth.breach import BreachChecker
from app.services.auth.codes import CodeCheck

router = APIRouter(tags=["account"])

WRONG_PASSWORD = ("wrong_password", "Mot de passe actuel incorrect.")


@router.get("/me", response_model=MeOut)
def read_me(user: User = Depends(get_current_user)) -> MeOut:
    return MeOut.model_validate(user)


@router.patch("/me", response_model=MeOut)
def update_me(payload: ProfileIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> MeOut:
    user.first_name, user.last_name = payload.first_name, payload.last_name
    db.commit()
    return MeOut.model_validate(user)


@router.post("/me/password", response_model=NoticeOut)
def change_password(payload: PasswordChangeIn, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user), auth: AuthSession = Depends(get_auth_session),
                    now: datetime = Depends(get_now), breach: BreachChecker = Depends(get_breach_checker)) -> NoticeOut:
    if not profile.password_ok(user, payload.current_password):
        raise fail(400, *WRONG_PASSWORD)  # avant Have I Been Pwned : pas de relais gratuit
    check_password_rules(payload.new_password, breach)
    profile.change_password(db, user, payload.new_password, keep_session=auth, now=now, ip=client_ip(request))
    db.commit()
    return NoticeOut(message="Mot de passe enregistré. Vos autres appareils ont été déconnectés.")


@router.post("/me/email", response_model=NoticeOut, status_code=202)
def request_email_change(payload: EmailChangeIn, request: Request, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user), now: datetime = Depends(get_now)) -> NoticeOut:
    if not profile.password_ok(user, payload.password):
        raise fail(400, *WRONG_PASSWORD)
    new_email = normalize_email(payload.new_email)
    if mail_allowed(db, new_email, client_ip(request) or "inconnue", now):
        profile.request_email_change(db, user, new_email, now)
    db.commit()
    return NoticeOut(message="Si cette adresse peut être utilisée, un code vient d'y être envoyé.")


@router.post("/me/email/verify", response_model=MeOut)
def confirm_email_change(payload: CodeIn, request: Request, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user), now: datetime = Depends(get_now)) -> MeOut:
    try:
        result = profile.confirm_email_change(db, user, payload.code, now, client_ip(request))
    except profile.EmailTaken:
        db.commit()  # le code est consommé : il faudra en redemander un
        raise fail(409, "email_taken", "Cette adresse vient d'être prise par un autre compte.")
    if result != CodeCheck.OK:
        db.commit()  # enregistre l'essai raté
        raise fail(400, *CODE_ERRORS[result])
    db.commit()
    return MeOut.model_validate(user)
