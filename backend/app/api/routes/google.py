"""Connexion Google : /start redirige vers Google, /callback revient avec le code (spec 2.5)."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_google_client
from app.api.origin import check_origin
from app.api.routes.auth import client_ip, fail, start_session
from app.core.config import get_settings
from app.core.current_user import get_now
from app.core.db import get_db
from app.core.security import new_token, pkce_challenge, sign, unsign
from app.schemas.auth import GoogleCompleteIn, GooglePendingOut, MeOut
from app.services.auth import accounts
from app.services.auth.google import GoogleClient, GoogleError, GoogleIdentity
from app.services.security_log import log_event

router = APIRouter(prefix="/auth/google", tags=["auth"])
OAUTH_COOKIE, PENDING_COOKIE, COOKIE_PATH = "pea_oauth", "pea_google_pending", "/api/auth/google"
OAUTH_MAX_AGE, PENDING_MAX_AGE = timedelta(minutes=10), timedelta(minutes=30)


def safe_next(value: str | None) -> str:
    """Chemin interne seulement (même règle que le frontend) : sinon l'accueil."""
    if not value or not value.startswith("/") or value.startswith("//") or value.startswith("/\\"):
        return "/"
    return value


def _redirect_uri() -> str:
    return get_settings().public_base_url.rstrip("/") + "/api/auth/google/callback"


def _set_cookie(response: Response, name: str, value: str, max_age: timedelta) -> None:
    response.set_cookie(name, value, max_age=int(max_age.total_seconds()), path=COOKIE_PATH, httponly=True,
                        secure=get_settings().cookie_secure, samesite="lax")


def _require(google: GoogleClient | None) -> GoogleClient:
    if google is None:
        raise HTTPException(404, detail={"code": "google_disabled", "message": "Connexion Google non configurée."})
    return google


@router.get("/start")
def start(suite: str | None = None, remember: bool = True, now: datetime = Depends(get_now),
          google: GoogleClient | None = Depends(get_google_client)) -> RedirectResponse:
    client = _require(google)
    state, nonce, verifier = new_token(), new_token(), new_token()
    response = RedirectResponse(client.authorize_url(state=state, nonce=nonce, code_challenge=pkce_challenge(verifier),
                                                     redirect_uri=_redirect_uri()), status_code=302)
    _set_cookie(response, OAUTH_COOKIE, sign({"state": state, "nonce": nonce, "verifier": verifier,
                                              "suite": safe_next(suite), "remember": remember},
                                             get_settings().app_secret, now), OAUTH_MAX_AGE)
    return response


def _error(kind: str = "google") -> RedirectResponse:
    response = RedirectResponse(f"/connexion?erreur={kind}", status_code=302)
    response.delete_cookie(OAUTH_COOKIE, path=COOKIE_PATH)
    return response


@router.get("/callback")
def callback(request: Request, state: str | None = None, code: str | None = None, db: Session = Depends(get_db),
             now: datetime = Depends(get_now), google: GoogleClient | None = Depends(get_google_client)) -> Response:
    client = _require(google)
    flow = unsign(request.cookies.get(OAUTH_COOKIE), get_settings().app_secret, now, OAUTH_MAX_AGE)
    if flow is None or not state or not code or state != flow["state"] or accounts.oauth_state_used(db, state, now):
        return _error()
    try:
        identity = client.identify(code=code, code_verifier=flow["verifier"], nonce=flow["nonce"],
                                   redirect_uri=_redirect_uri())
    except GoogleError:
        return _error()
    if not identity.email_verified or not identity.email:
        return _error("google_email")
    user = accounts.google_sign_in(db, identity, now, ip=client_ip(request))
    if user is None:
        response = RedirectResponse("/finaliser-inscription", status_code=302)
        _set_cookie(response, PENDING_COOKIE, sign({"sub": identity.sub, "email": identity.email,
                                                    "first_name": identity.first_name, "last_name": identity.last_name},
                                                   get_settings().app_secret, now), PENDING_MAX_AGE)
        db.commit()
    else:
        log_event(db, "login_ok", now=now, user_id=user.id, ip=client_ip(request), details={"method": "google"})
        response = RedirectResponse(flow["suite"], status_code=302)
        start_session(db, user, request, response, persistent=bool(flow["remember"]), now=now, alert_new_device=True)
    response.delete_cookie(OAUTH_COOKIE, path=COOKIE_PATH)
    return response


@router.get("/pending", response_model=GooglePendingOut)
def pending(request: Request, now: datetime = Depends(get_now),
            google: GoogleClient | None = Depends(get_google_client)) -> GooglePendingOut:
    _require(google)
    data = unsign(request.cookies.get(PENDING_COOKIE), get_settings().app_secret, now, PENDING_MAX_AGE)
    if data is None:
        raise HTTPException(404, detail={"code": "google_expired", "message": "Recommencez la connexion avec Google."})
    return GooglePendingOut(email=data["email"], first_name=data["first_name"], last_name=data["last_name"])


@router.post("/complete", response_model=MeOut, dependencies=[Depends(check_origin)])
def complete(payload: GoogleCompleteIn, request: Request, response: Response, db: Session = Depends(get_db),
             now: datetime = Depends(get_now), google: GoogleClient | None = Depends(get_google_client)) -> MeOut:
    _require(google)  # Google éteint (ou APP_SECRET vide) : aucun cookie « en attente » n'est accepté
    data = unsign(request.cookies.get(PENDING_COOKIE), get_settings().app_secret, now, PENDING_MAX_AGE)
    if data is None:
        raise fail(400, "google_expired", "Recommencez la connexion avec Google.")
    identity = GoogleIdentity(sub=data["sub"], email=data["email"], email_verified=True,
                              first_name=data["first_name"], last_name=data["last_name"])
    ip = client_ip(request)
    user = accounts.google_sign_in(db, identity, now, ip=ip)  # compte apparu entre-temps : simple connexion
    if user is None:
        user = accounts.create_google_account(db, identity, first_name=payload.first_name,
                                              last_name=payload.last_name, now=now)
        log_event(db, "google_signup", now=now, user_id=user.id, ip=ip)
    response.delete_cookie(PENDING_COOKIE, path=COOKIE_PATH)
    start_session(db, user, request, response, persistent=True, now=now, alert_new_device=False)
    return MeOut.model_validate(user)
