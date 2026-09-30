from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import verify_password
from app.models import AuthSession, EmailCode, EmailLog, User
from app.services.auth.codes import issue_code
from app.services.auth.sessions import open_session
from tests.factories import make_user

PASSWORD = "motdepasse-solide"
NEW = "un-nouveau-mot-de-passe-long"
NOW = datetime.now(UTC)


def mails(db, kind):
    return db.scalars(select(EmailLog).where(EmailLog.kind == kind)).all()


def test_rename(client, user):
    body = client.patch("/api/me", json={"first_name": " Jeanne ", "last_name": "Durand"}).json()
    assert (body["first_name"], body["last_name"]) == ("Jeanne", "Durand")
    assert client.patch("/api/me", json={"first_name": "", "last_name": "x"}).status_code == 422


def test_change_password_needs_the_current_one(client, user):
    wrong = client.post("/api/me/password", json={"current_password": "pas-le-bon-mot-de-passe", "new_password": NEW})
    assert wrong.status_code == 400 and wrong.json()["detail"]["code"] == "wrong_password"
    missing = client.post("/api/me/password", json={"new_password": NEW})
    assert missing.status_code == 400 and missing.json()["detail"]["code"] == "wrong_password"


def test_change_password_signs_out_other_devices_and_alerts(client, db, user):
    current = db.scalar(select(AuthSession).where(AuthSession.user_id == user.id))  # session du client de test
    open_session(db, user, persistent=True, ip="198.51.100.1", user_agent="autre", now=NOW, settings=get_settings())
    assert client.post("/api/me/password", json={"current_password": PASSWORD, "new_password": NEW}).status_code == 200
    db.expire_all()
    assert verify_password(db.get(User, user.id).password_hash, NEW)
    remaining = db.scalars(select(AuthSession).where(AuthSession.user_id == user.id)).all()
    assert [s.id for s in remaining] == [current.id]  # celle-ci reste ouverte
    assert [m.recipient for m in mails(db, "security_alert")] == [user.email]


def test_change_password_rules_apply(client, fake_breach):
    short = client.post("/api/me/password", json={"current_password": PASSWORD, "new_password": "court"})
    assert short.json()["detail"]["code"] == "weak_password"
    fake_breach.pwned.add(NEW)
    pwned = client.post("/api/me/password", json={"current_password": PASSWORD, "new_password": NEW})
    assert pwned.json()["detail"]["code"] == "pwned_password"


def test_google_account_can_add_a_password(client, db, user):
    user.password_hash, user.google_sub = None, "sub-1"
    db.flush()
    assert client.post("/api/me/password", json={"new_password": NEW}).status_code == 200
    assert client.get("/api/me").json()["has_password"] is True


def test_email_change_sends_a_code_to_the_new_address(client, db, user):
    response = client.post("/api/me/email", json={"new_email": "Nouveau@Example.com", "password": PASSWORD})
    assert response.status_code == 202
    assert [m.recipient for m in mails(db, "verify_code")] == ["nouveau@example.com"]
    row = db.scalar(select(EmailCode).where(EmailCode.purpose == "change_email"))
    assert row.new_email == "nouveau@example.com"


def test_email_change_needs_the_password(client, db):
    response = client.post("/api/me/email", json={"new_email": "nouveau@example.com", "password": "faux-mot-de-passe"})
    assert response.status_code == 400 and response.json()["detail"]["code"] == "wrong_password"
    assert mails(db, "verify_code") == []


def test_email_change_to_taken_address_sends_nothing(client, db):
    make_user(db, "prise@example.com")
    response = client.post("/api/me/email", json={"new_email": "prise@example.com", "password": PASSWORD})
    assert response.status_code == 202  # même réponse : ne révèle pas le compte
    assert mails(db, "verify_code") == []


def test_email_verify_switches_address_and_alerts_the_old_one(client, db, user, monkeypatch):
    import app.services.auth.codes as codes

    monkeypatch.setattr(codes, "new_code", lambda: "123456")
    client.post("/api/me/email", json={"new_email": "nouveau@example.com", "password": PASSWORD})
    wrong = client.post("/api/me/email/verify", json={"code": "000000"})
    assert wrong.status_code == 400 and wrong.json()["detail"]["code"] == "invalid_code"
    body = client.post("/api/me/email/verify", json={"code": "123456"}).json()
    assert body["email"] == "nouveau@example.com"
    assert [m.recipient for m in mails(db, "security_alert")] == ["moi@example.com"]


def test_email_verify_signs_out_other_devices(client, db, user):
    current = db.scalar(select(AuthSession).where(AuthSession.user_id == user.id))
    open_session(db, user, persistent=True, ip="198.51.100.1", user_agent="autre", now=NOW, settings=get_settings())
    code = issue_code(db, user, "change_email", NOW, new_email="nouveau@example.com")
    assert client.post("/api/me/email/verify", json={"code": code}).status_code == 200
    remaining = db.scalars(select(AuthSession).where(AuthSession.user_id == user.id)).all()
    assert [s.id for s in remaining] == [current.id]


def test_email_verify_refuses_an_address_taken_meanwhile(client, db, user):
    code = issue_code(db, user, "change_email", NOW, new_email="course@example.com")
    make_user(db, "course@example.com")
    response = client.post("/api/me/email/verify", json={"code": code})
    assert response.status_code == 409 and response.json()["detail"]["code"] == "email_taken"
    assert db.get(User, user.id).email == "moi@example.com"


def test_profile_routes_need_a_session(anon_client):
    assert anon_client.patch("/api/me", json={"first_name": "a", "last_name": "b"}).status_code == 401
    assert anon_client.post("/api/me/password", json={"new_password": NEW}).status_code == 401
