import re

from sqlalchemy import func, select

from app.models import AuthSession, EmailLog
from app.services.auth.sessions import DEVICE_COOKIE, SESSION_COOKIE
from tests.factories import make_user

PASSWORD = "motdepasse-solide"


def _login(client, email="jean@example.com", password=PASSWORD, remember=False):
    return client.post("/api/auth/login", json={"email": email, "password": password, "remember": remember})


def _mails(db, kind):
    return db.scalars(select(EmailLog).where(EmailLog.kind == kind).order_by(EmailLog.id)).all()


def _token(mail: EmailLog) -> str:
    return re.search(r"jeton=([\w-]+)", mail.text).group(1)


def test_login_sets_cookies_and_me_works(anon_client, db):
    make_user(db, "jean@example.com")
    response = _login(anon_client, "  JEAN@example.com ", remember=True)
    assert response.status_code == 200 and response.json()["email"] == "jean@example.com"
    assert {SESSION_COOKIE, "pea_csrf", DEVICE_COOKIE} <= set(response.cookies)
    assert anon_client.get("/api/me").status_code == 200


def test_bad_credentials_look_the_same(anon_client, db):
    make_user(db, "jean@example.com")
    wrong_password = _login(anon_client, password="mauvais-mot-de-passe")
    unknown = _login(anon_client, email="personne@example.com")
    assert wrong_password.status_code == unknown.status_code == 401
    assert wrong_password.json() == unknown.json()
    assert wrong_password.json()["detail"]["code"] == "invalid_credentials"


def test_unverified_account_is_sent_to_validation(anon_client, db):
    make_user(db, "jean@example.com", verified=False)
    response = _login(anon_client)
    assert response.status_code == 403 and response.json()["detail"]["code"] == "email_not_verified"
    assert SESSION_COOKIE not in response.cookies
    assert len(_mails(db, "verify_code")) == 1


def test_logout_revokes_the_session(anon_client, db):
    make_user(db, "jean@example.com")
    _login(anon_client)
    anon_client.headers["X-CSRF-Token"] = anon_client.cookies["pea_csrf"]
    assert anon_client.post("/api/auth/logout").status_code == 204
    assert db.scalar(select(func.count()).select_from(AuthSession)) == 0
    assert anon_client.get("/api/me").status_code == 401


def test_new_device_alert_only_from_the_second_browser(anon_client, db):
    make_user(db, "jean@example.com")
    _login(anon_client)                  # premier appareil du compte : pas d'alerte
    _login(anon_client)                  # même navigateur (cookie pea_device) : pas d'alerte
    assert _mails(db, "new_device") == []
    anon_client.cookies.clear()
    _login(anon_client)                  # autre navigateur
    assert len(_mails(db, "new_device")) == 1


def test_not_me_closes_everything_and_forces_a_new_password(anon_client, db):
    user = make_user(db, "jean@example.com")
    _login(anon_client)
    anon_client.cookies.clear()
    _login(anon_client)
    token = _token(_mails(db, "new_device")[0])
    anon_client.cookies.clear()
    anon_client.headers.pop("X-CSRF-Token", None)
    assert anon_client.post("/api/auth/not-me", json={"token": token}).status_code == 200
    assert db.scalar(select(func.count()).select_from(AuthSession)) == 0
    db.refresh(user)
    assert user.password_hash is None and len(_mails(db, "reset_password")) == 1
    assert _login(anon_client).status_code == 401
    assert anon_client.post("/api/auth/not-me", json={"token": token}).status_code == 400  # usage unique


def test_forgot_and_reset_password(anon_client, db):
    make_user(db, "jean@example.com")
    _login(anon_client)
    same_answer = anon_client.post("/api/auth/forgot-password", json={"email": "personne@example.com"})
    response = anon_client.post("/api/auth/forgot-password", json={"email": "jean@example.com"})
    assert response.status_code == same_answer.status_code == 202 and response.json() == same_answer.json()
    token = _token(_mails(db, "reset_password")[0])
    weak = anon_client.post("/api/auth/reset-password", json={"token": token, "password": "court"})
    assert weak.status_code == 400 and weak.json()["detail"]["code"] == "weak_password"
    ok = anon_client.post("/api/auth/reset-password", json={"token": token, "password": "nouveau-mot-de-passe"})
    assert ok.status_code == 200
    assert db.scalar(select(func.count()).select_from(AuthSession)) == 0  # tous les appareils déconnectés
    assert [m.kind for m in _mails(db, "security_alert")] == ["security_alert"]
    assert _login(anon_client, password="nouveau-mot-de-passe").status_code == 200
    again = anon_client.post("/api/auth/reset-password", json={"token": token, "password": "encore-un-autre-mdp"})
    assert again.status_code == 400 and again.json()["detail"]["code"] == "invalid_token"


def test_login_replaces_a_previous_session(anon_client, db):
    make_user(db, "jean@example.com")
    _login(anon_client)
    anon_client.headers["X-CSRF-Token"] = anon_client.cookies["pea_csrf"]
    _login(anon_client)
    assert db.scalar(select(func.count()).select_from(AuthSession)) == 1
