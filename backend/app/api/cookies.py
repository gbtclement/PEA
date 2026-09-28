from datetime import timedelta

from fastapi import Response

from app.core.config import Settings
from app.services.auth.sessions import CSRF_COOKIE, DEVICE_COOKIE, SESSION_COOKIE, NewSession

DEVICE_MAX_AGE = int(timedelta(days=365).total_seconds())


def set_auth_cookies(response: Response, new: NewSession, settings: Settings) -> None:
    # Sans « rester connecté », cookies de session du navigateur (effacés à sa fermeture).
    max_age = int(timedelta(days=settings.session_days).total_seconds()) if new.session.persistent else None
    common = dict(max_age=max_age, secure=settings.cookie_secure, samesite="lax", path="/")
    response.set_cookie(SESSION_COOKIE, new.token, httponly=True, **common)
    response.set_cookie(CSRF_COOKIE, new.csrf_token, httponly=False, **common)  # lu par le JavaScript


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    for name, httponly in ((SESSION_COOKIE, True), (CSRF_COOKIE, False)):
        response.delete_cookie(name, path="/", secure=settings.cookie_secure, httponly=httponly, samesite="lax")


def set_device_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(DEVICE_COOKIE, token, max_age=DEVICE_MAX_AGE, httponly=True, secure=settings.cookie_secure,
                        samesite="lax", path="/")
