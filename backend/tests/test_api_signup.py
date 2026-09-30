import re

from sqlalchemy import select

from app.models import EmailLog, User
from app.services.auth.sessions import SESSION_COOKIE
from tests.factories import make_user

FORM = {"first_name": "Jean", "last_name": "Dupont", "email": "Jean@Example.com",
        "password": "motdepasse-solide", "accept_terms": True}


def _last_code(db, email="jean@example.com") -> str:
    mail = db.scalars(select(EmailLog).where(EmailLog.recipient == email, EmailLog.kind == "verify_code")
                      .order_by(EmailLog.id.desc())).first()
    return re.search(r"\b(\d{6})\b", mail.subject).group(1)


def test_signup_then_verify_opens_a_session(anon_client, db):
    response = anon_client.post("/api/auth/register", json=FORM)
    assert response.status_code == 202 and SESSION_COOKIE not in response.cookies
    user = db.scalar(select(User).where(User.email == "jean@example.com"))
    assert user.email_verified_at is None and user.terms_version == "2026-09-28"
    verified = anon_client.post("/api/auth/verify-email", json={"email": "jean@example.com", "code": _last_code(db)})
    assert verified.status_code == 200 and verified.json()["email"] == "jean@example.com"
    assert SESSION_COOKIE in verified.cookies and "pea_csrf" in verified.cookies
    assert anon_client.get("/api/me").status_code == 200
    kinds = [m.kind for m in db.scalars(select(EmailLog).order_by(EmailLog.id))]
    assert kinds == ["verify_code", "welcome"]


def test_existing_account_gets_same_answer_and_an_alert(anon_client, db):
    make_user(db, "jean@example.com")
    fresh = anon_client.post("/api/auth/register", json={**FORM, "email": "nouveau@example.com"})
    taken = anon_client.post("/api/auth/register", json=FORM)
    assert (taken.status_code, taken.json(), dict(taken.cookies)) == (fresh.status_code, fresh.json(), dict(fresh.cookies))
    alert = db.scalars(select(EmailLog).where(EmailLog.recipient == "jean@example.com")).one()
    assert alert.kind == "security_alert"


def test_wrong_code_and_errors(anon_client, db):
    anon_client.post("/api/auth/register", json=FORM)
    code = _last_code(db)
    wrong = "000000" if code != "000000" else "111111"
    response = anon_client.post("/api/auth/verify-email", json={"email": "jean@example.com", "code": wrong})
    assert response.status_code == 400 and response.json()["detail"]["code"] == "invalid_code"
    unknown = anon_client.post("/api/auth/verify-email", json={"email": "personne@example.com", "code": code})
    assert unknown.status_code == 400 and unknown.json()["detail"]["code"] == "invalid_code"


def test_signup_rules(anon_client):
    assert anon_client.post("/api/auth/register", json={**FORM, "accept_terms": False}).status_code == 422
    weak = anon_client.post("/api/auth/register", json={**FORM, "password": "court"})
    assert weak.status_code == 400 and weak.json()["detail"]["code"] == "weak_password"
    assert anon_client.post("/api/auth/register", json={**FORM, "email": "pas-une-adresse"}).status_code == 422
    assert anon_client.post("/api/auth/register", json={**FORM, "first_name": "   "}).status_code == 422


def test_signing_up_again_before_validation_replaces_the_pending_account(anon_client, db):
    anon_client.post("/api/auth/register", json=FORM)
    anon_client.post("/api/auth/register", json={**FORM, "first_name": "Jeanne"})
    users = db.scalars(select(User).where(User.email == "jean@example.com")).all()
    assert len(users) == 1 and users[0].first_name == "Jeanne"


def test_resend_code_waits_60_seconds_and_hides_unknown_addresses(anon_client, db):
    anon_client.post("/api/auth/register", json=FORM)
    first = anon_client.post("/api/auth/resend-code", json={"email": "jean@example.com"})
    unknown = anon_client.post("/api/auth/resend-code", json={"email": "personne@example.com"})
    assert first.status_code == unknown.status_code == 202 and first.json() == unknown.json()
    # moins de 60 s après l'inscription : pas de deuxième code
    assert len(db.scalars(select(EmailLog).where(EmailLog.kind == "verify_code")).all()) == 1


def test_admin_email_becomes_admin_on_validation(anon_client, db, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.get_settings(), "admin_email", "jean@example.com")
    anon_client.post("/api/auth/register", json=FORM)
    anon_client.post("/api/auth/verify-email", json={"email": "jean@example.com", "code": _last_code(db)})
    assert anon_client.get("/api/me").json()["role"] == "admin"


def test_existing_account_costs_the_same_hashing_time(anon_client, db, monkeypatch):
    """Sans hachage pour une adresse déjà prise, la réponse serait plus rapide et trahirait le compte."""
    from app.services.auth import accounts
    calls = []
    monkeypatch.setattr(accounts, "hash_password", lambda password: calls.append(password) or "haché")
    make_user(db, "jean@example.com")
    anon_client.post("/api/auth/register", json=FORM)
    assert calls == [FORM["password"]]
